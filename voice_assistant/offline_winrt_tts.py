"""Access downloaded, on-device Windows Narrator voices from Python."""

import asyncio
try:
    from winrt.runtime import ApartmentType, init_apartment
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader
except ImportError:
    ApartmentType = None
    init_apartment = None
    SpeechSynthesizer = None
    DataReader = None


def find_voice(name):
    if SpeechSynthesizer is None:
        return None
    try:
        if init_apartment:
            try:
                init_apartment(ApartmentType.MULTI_THREADED)
            except OSError:
                pass  # The caller may already have initialized its COM apartment.
        wanted = name.casefold()
        voices = list(SpeechSynthesizer.all_voices)
        return next(
            (voice for voice in voices if voice.display_name.casefold() == wanted),
            next((voice for voice in voices if wanted in voice.display_name.casefold()), None),
        )
    except Exception:
        return None


async def _synthesize(text, output_file, preferred_voice):
    voice = find_voice(preferred_voice)
    if voice is None:
        raise RuntimeError(
            f"Windows voice '{preferred_voice}' is not installed or available to Friday. "
            "Download it under Settings > Accessibility > Narrator > Add a natural voice."
        )

    synthesizer = SpeechSynthesizer()
    speech_stream = None
    reader = None
    try:
        synthesizer.voice = voice
        speech_stream = await synthesizer.synthesize_text_to_stream_async(text)
        size = int(speech_stream.size)
        if size < 44:
            raise RuntimeError("Windows returned an empty or invalid speech stream")

        reader = DataReader(speech_stream.get_input_stream_at(0))
        remaining = size
        with open(output_file, "wb") as output:
            while remaining:
                chunk_size = min(64 * 1024, remaining)
                await reader.load_async(chunk_size)
                chunk = bytearray(chunk_size)
                reader.read_bytes(chunk)
                output.write(chunk)
                remaining -= chunk_size
    finally:
        if reader is not None:
            reader.close()
        if speech_stream is not None:
            speech_stream.close()
        synthesizer.close()


def synthesize(text, output_file, preferred_voice="Microsoft Ava"):
    asyncio.run(_synthesize(text, output_file, preferred_voice))
