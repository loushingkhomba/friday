"""Offline, consent-based speaker profiles using a local WeSpeaker ONNX model."""

import json
import os
import re
import tempfile

import numpy as np
from scipy.signal import resample_poly


MODEL_NAME = "Wespeaker/wespeaker-voxceleb-resnet34-LM"
MODEL_LICENSE = "CC-BY-4.0 (VoxCeleb dataset)"
MIN_AUDIO_SECONDS = 3.0
MIN_IDENTIFICATION_SECONDS = 2.0
MATCH_THRESHOLD = 0.62
MATCH_MARGIN = 0.08
CONTINUITY_THRESHOLD = 0.58
VOICE_CHANGE_SIMILARITY = 0.78
MAX_PROFILE_EMBEDDINGS = 24


def _mel(frequency):
    return 1127.0 * np.log1p(np.asarray(frequency, dtype=np.float64) / 700.0)


def _fbank(samples, sample_rate=16000, mel_bins=80):
    """Extract WeSpeaker-compatible 25 ms/10 ms Kaldi-style log filterbanks."""
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if sample_rate != 16000:
        divisor = np.gcd(sample_rate, 16000)
        samples = resample_poly(samples, 16000 // divisor, sample_rate // divisor).astype(np.float32)

    frame_length = 400
    frame_shift = 160
    if samples.size < frame_length:
        raise ValueError("Not enough audio was captured for voice comparison.")

    frame_count = 1 + (samples.size - frame_length) // frame_shift
    frames = np.lib.stride_tricks.sliding_window_view(samples, frame_length)[::frame_shift][:frame_count].copy()
    frames -= np.mean(frames, axis=1, keepdims=True)
    frames[:, 1:] -= 0.97 * frames[:, :-1].copy()
    frames *= np.hamming(frame_length).astype(np.float32)

    spectrum = np.fft.rfft(frames, n=512, axis=1)
    power = (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float64)
    frequencies = np.arange(257, dtype=np.float64) * (sample_rate / 512.0)
    mel_frequencies = np.linspace(_mel(20.0), _mel(sample_rate / 2.0), mel_bins + 2)
    mel_frequencies_hz = 700.0 * (np.exp(mel_frequencies / 1127.0) - 1.0)

    filters = np.zeros((mel_bins, frequencies.size), dtype=np.float64)
    for index in range(mel_bins):
        left, center, right = mel_frequencies_hz[index:index + 3]
        filters[index] = np.maximum(
            0.0,
            np.minimum((frequencies - left) / max(center - left, 1e-12),
                       (right - frequencies) / max(right - center, 1e-12)),
        )

    energies = power @ filters.T
    features = np.log(np.maximum(energies, 1e-10)).astype(np.float32)
    features -= features.mean(axis=0, keepdims=True)
    return features[None, :, :]


class SpeakerProfiles:
    """Store speaker labels and voice embeddings; never persist raw recordings."""

    def __init__(self, profiles_path, model_path, store=None):
        self.profiles_path = profiles_path
        self.store = store
        self.model_path = model_path
        self._session = None
        self._input_name = None
        self._output_name = None
        self.last_match_used_continuity = False
        self.last_match_diagnostics = None
        self.data = self._load()

    def _load(self):
        if self.store is not None:
            try:
                stored = self.store.load_profile_bundle()
                if stored.get("profiles"):
                    stored.setdefault("model", MODEL_NAME)
                    stored.setdefault("model_license", MODEL_LICENSE)
                    return stored
            except Exception:
                raise
        try:
            with open(self.profiles_path, "r", encoding="utf-8") as profile_file:
                data = json.load(profile_file)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        profiles = data.get("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
        data["profiles"] = profiles
        data.setdefault("version", 1)
        data.setdefault("onboarding_complete", False)
        data.setdefault("model", MODEL_NAME)
        data.setdefault("model_license", MODEL_LICENSE)
        return data

    @property
    def onboarding_complete(self):
        return bool(self.data.get("onboarding_complete"))

    @property
    def has_profiles(self):
        return bool(self.data.get("profiles"))

    def _save(self):
        if self.store is not None:
            self.store.save_profile_bundle(self.data)
            return
        directory = os.path.dirname(self.profiles_path)
        os.makedirs(directory, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(prefix="speaker_profiles_", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as profile_file:
                json.dump(self.data, profile_file, indent=2, ensure_ascii=False)
                profile_file.flush()
                os.fsync(profile_file.fileno())
            os.replace(temporary_path, self.profiles_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def complete_first_onboarding(self):
        self.data["onboarding_complete"] = True
        self._save()

    def remember_dislike(self, label, subject):
        """Persist an explicit avoid preference only on the named local profile."""
        key = str(label or '').casefold()
        profile = self.data.get('profiles', {}).get(key)
        subject = re.sub(r'\s+', ' ', str(subject or '')).strip(' .,!?:;')[:180]
        if not isinstance(profile, dict) or not subject:
            return False, False
        details = profile.setdefault('details', {})
        if not isinstance(details, dict):
            details = profile['details'] = {}
        dislikes = details.get('dislikes', [])
        if isinstance(dislikes, str):
            dislikes = [dislikes]
        if not isinstance(dislikes, list):
            dislikes = []
        already_saved = any(str(item).casefold() == subject.casefold() for item in dislikes)
        if not already_saved:
            dislikes.append(subject)
        details['dislikes'] = dislikes
        self._save()
        return True, already_saved

    def _load_model(self):
        if self._session is not None:
            return
        if not os.path.isfile(self.model_path):
            raise RuntimeError("Friday's local speaker model is missing. It will not download anything at runtime.")
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            self.model_path,
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()
        if not inputs or not outputs:
            raise RuntimeError("Friday's local speaker model has no usable inputs or outputs.")
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name

    @staticmethod
    def _audio_samples(audio, minimum_seconds=MIN_AUDIO_SECONDS):
        if audio is None:
            raise ValueError("No microphone audio was captured.")
        raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if samples.size / 16000 < minimum_seconds:
            raise ValueError(f"That sample was too short. Please speak for at least {minimum_seconds:g} seconds.")
        return samples

    @staticmethod
    def audio_quality(audio):
        """Return numeric audio diagnostics only; never persist the recording."""
        if audio is None:
            return {'duration_seconds': 0.0, 'rms': 0.0, 'peak': 0.0, 'clipped_fraction': 0.0}
        raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
        if not samples.size:
            return {'duration_seconds': 0.0, 'rms': 0.0, 'peak': 0.0, 'clipped_fraction': 0.0}
        magnitude = np.abs(samples)
        return {
            'duration_seconds': samples.size / 16000.0,
            'rms': float(np.sqrt(np.mean(samples ** 2))),
            'peak': float(np.max(magnitude)),
            'clipped_fraction': float(np.mean(magnitude >= 0.999)),
        }

    @staticmethod
    def voice_change_signature(audio):
        """Cheap, transient spectral signature used to decide when to re-identify."""
        samples = SpeakerProfiles._audio_samples(audio, minimum_seconds=0.75)
        frame_length = 400
        frame_shift = 160
        if samples.size < frame_length:
            raise ValueError("Not enough speech for a voice-change check.")
        frames = np.lib.stride_tricks.sliding_window_view(samples, frame_length)[::frame_shift].copy()
        frames -= np.mean(frames, axis=1, keepdims=True)
        frames *= np.hamming(frame_length).astype(np.float32)
        power = np.abs(np.fft.rfft(frames, n=512, axis=1)) ** 2
        frequencies = np.arange(power.shape[1], dtype=np.float32) * 16000 / 512
        edges = (80, 250, 500, 1000, 2000, 3500, 5000, 7600)
        band_energy = [
            np.median(np.sum(power[:, (frequencies >= low) & (frequencies < high)], axis=1))
            for low, high in zip(edges, edges[1:])
        ]
        signature = np.log(np.maximum(np.asarray(band_energy, dtype=np.float32), 1e-8))
        signature -= signature.mean()
        norm = float(np.linalg.norm(signature))
        if norm <= 1e-8:
            raise ValueError("Could not measure a stable voice signature.")
        return signature / norm

    def embed(self, audio, minimum_seconds=MIN_AUDIO_SECONDS):
        self._load_model()
        samples = self._audio_samples(audio, minimum_seconds=minimum_seconds)
        features = _fbank(samples)
        result = self._session.run([self._output_name], {self._input_name: features})[0]
        embedding = np.asarray(result, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(embedding))
        if norm <= 1e-8:
            raise ValueError("Friday could not get a clear voice sample. Please try again.")
        return embedding / norm

    @staticmethod
    def audio_seconds(audio):
        if audio is None or not audio.sample_rate or not audio.sample_width:
            return 0.0
        return len(audio.frame_data) / (audio.sample_rate * audio.sample_width)

    @staticmethod
    def _safe_label(label):
        label = re.sub(r"\s+", " ", str(label)).strip()
        if not label or len(label) > 64 or any(ord(char) < 32 for char in label):
            raise ValueError("Profile name must be 1 to 64 characters.")
        return label

    def enroll(self, label, audio_samples):
        label = self._safe_label(label)
        vectors = [self.embed(sample) for sample in audio_samples]
        return self.enroll_embeddings(label, vectors)

    def enroll_embeddings(self, label, embeddings, details=None, device_name=None):
        label = self._safe_label(label)
        new_vectors = [np.asarray(vector, dtype=np.float32).reshape(-1) for vector in embeddings]
        if len(new_vectors) < 6:
            raise ValueError("Friday needs six clear samples before saving a voice profile.")
        key = label.casefold()
        previous = self.data["profiles"].get(key, {})
        prior_vectors = previous.get("embeddings")
        if not isinstance(prior_vectors, list) or not prior_vectors:
            prior_vectors = [previous.get("embedding", [])] if previous.get("embedding") else []
        vectors = []
        for raw_vector in [*prior_vectors, *new_vectors]:
            vector = np.asarray(raw_vector, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(vector))
            if norm > 1e-8:
                vectors.append(vector / norm)
        vectors = vectors[-MAX_PROFILE_EMBEDDINGS:]
        average = np.mean(np.stack(vectors), axis=0)
        average /= max(float(np.linalg.norm(average)), 1e-8)
        profile = {
            "name": label,
            "embedding": average.tolist(),
            # Keep bounded normalized examples across explicit re-enrollments.
            # This lets one profile cover normal voice variation and multiple mics.
            "embeddings": [vector.tolist() for vector in vectors],
        }
        prior_devices = previous.get("enrollment_devices", [])
        devices = [str(item) for item in prior_devices if str(item).strip()] if isinstance(prior_devices, list) else []
        new_devices = [device_name] if isinstance(device_name, str) else list(device_name or [])
        for item in new_devices:
            device = str(item).strip()[:160]
            if device and device not in devices:
                devices.append(device)
        if devices:
            profile["enrollment_devices"] = devices[-8:]
        # Re-enrollment refreshes voice data only. Preserve existing details,
        # updating a field only when user supplies a replacement value.
        saved_details = dict(previous.get("details", {})) if isinstance(previous.get("details"), dict) else {}
        if isinstance(details, dict):
            for field, value in details.items():
                if field in {"interests", "assistance", "reply_style"} and str(value).strip():
                    saved_details[field] = value
                elif field == 'dislikes' and isinstance(value, list):
                    saved_details[field] = value
        if saved_details:
            normalized_details = {}
            for field, value in saved_details.items():
                if field in {"interests", "assistance", "reply_style"} and str(value).strip():
                    normalized_details[str(field)] = re.sub(r"\s+", " ", str(value)).strip()[:400]
                elif field == 'dislikes' and isinstance(value, list):
                    normalized_details[field] = [
                        re.sub(r'\s+', ' ', str(item)).strip()[:180]
                        for item in value if str(item).strip()
                    ]
            if normalized_details:
                profile["details"] = normalized_details
        self.data["profiles"][key] = profile
        self.data["onboarding_complete"] = True
        self._save()
        return label

    def identify(self, audio, continuity_name=None):
        self.last_match_used_continuity = False
        self.last_match_diagnostics = None
        if not self.has_profiles:
            return None, None
        candidate = self.embed(audio, minimum_seconds=MIN_IDENTIFICATION_SECONDS)
        ranked = []
        for profile in self.data["profiles"].values():
            raw_examples = profile.get("embeddings")
            if not isinstance(raw_examples, list) or not raw_examples:
                raw_examples = [profile.get("embedding", [])]
            examples = []
            for raw_example in raw_examples:
                stored = np.asarray(raw_example, dtype=np.float32).reshape(-1)
                if stored.shape == candidate.shape and float(np.linalg.norm(stored)) > 1e-8:
                    examples.append(stored / float(np.linalg.norm(stored)))
            if not examples:
                continue
            example_scores = sorted(
                (float(np.dot(candidate, stored)) for stored in examples), reverse=True
            )
            # Average two closest examples to avoid one noisy example deciding identity.
            score = float(np.mean(example_scores[:min(2, len(example_scores))]))
            ranked.append((score, profile.get("name", "")))
        ranked.sort(reverse=True)
        if not ranked:
            return None, None
        best_score, best_name = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else -1.0
        margin_ok = best_score - second_score >= MATCH_MARGIN
        diagnostics = {
            'best_profile': best_name,
            'best_score': best_score,
            'second_profile': ranked[1][1] if len(ranked) > 1 else None,
            'second_score': second_score if len(ranked) > 1 else None,
            'margin': best_score - second_score if len(ranked) > 1 else None,
            'required_margin': MATCH_MARGIN,
            'match_threshold': MATCH_THRESHOLD,
            'continuity_threshold': CONTINUITY_THRESHOLD,
        }
        if best_score < MATCH_THRESHOLD:
            if (continuity_name and best_name.casefold() == continuity_name.casefold()
                    and best_score >= CONTINUITY_THRESHOLD and margin_ok):
                self.last_match_used_continuity = True
                diagnostics['decision'] = 'matched_by_continuity'
                self.last_match_diagnostics = diagnostics
                return best_name, best_score
            diagnostics['decision'] = 'below_threshold'
            self.last_match_diagnostics = diagnostics
            return None, best_score
        if not margin_ok:
            diagnostics['decision'] = 'ambiguous_margin'
            self.last_match_diagnostics = diagnostics
            return None, best_score
        diagnostics['decision'] = 'matched'
        self.last_match_diagnostics = diagnostics
        return best_name, best_score

    def remove(self, label=None):
        profiles = self.data["profiles"]
        if label:
            key = str(label).casefold()
            if key not in profiles:
                return False
            del profiles[key]
        else:
            profiles.clear()
        self.data["onboarding_complete"] = True
        self._save()
        return True
