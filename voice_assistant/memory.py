import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GRPC_VERBOSITY'] = 'error'
os.environ['KMP_WARNINGS'] = '0'

import logging
for lg in ['grpc', 'tensorflow', 'keras']:
    logging.getLogger(lg).setLevel(logging.CRITICAL)

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
import uuid

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


class _CountProxy:
    def __init__(self, store, kind):
        self.store = store
        self.kind = kind

    def count(self):
        return self.store.count_memories(self.kind)


class MemoryModule:
    def __init__(self, persist_dir=None, store=None):
        self.store = store
        self.persist_dir = 'PostgreSQL (local)' if store else os.path.abspath(persist_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory_data'))
        self.embedding_model = None
        if SentenceTransformer is not None:
            try:
                self.embedding_model = SentenceTransformer(
                    'all-MiniLM-L6-v2', model_kwargs={'local_files_only': True}
                )
            except Exception:
                logging.getLogger(__name__).warning('Local embedding model unavailable; using text search only.')
        if store:
            self.semantic = _CountProxy(store, 'semantic')
            self.episodic = _CountProxy(store, 'episode')
            self.preferences = _CountProxy(store, 'preference')
            return
        import chromadb
        from chromadb.config import Settings
        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir, settings=Settings(anonymized_telemetry=False))
        self.semantic = self.client.get_or_create_collection('semantic')
        self.episodic = self.client.get_or_create_collection('episodic')
        self.preferences = self.client.get_or_create_collection('preferences')

    def embed(self, text):
        if self.embedding_model is None:
            return None
        return self.embedding_model.encode(text).tolist()

    def add_semantic(self, text, metadata=None):
        if not str(text).strip():
            return
        metadata = dict(metadata or {})
        metadata.setdefault('scope', 'shared')
        metadata['added'] = datetime.now().astimezone().isoformat(timespec='seconds')
        if self.store:
            stable_id = metadata.get('memory_id')
            self.store.save_memory(text, metadata.get('kind', 'semantic'), shared=True,
                                   metadata=metadata, embedding=self.embed(text), source='friday',
                                   memory_id=stable_id)
            return
        self.semantic.upsert(embeddings=[self.embed(text)], documents=[text], metadatas=[metadata],
                             ids=[f"sem_{uuid.uuid4().hex}"])

    def add_episode(self, text, metadata=None):
        metadata = dict(metadata or {})
        speaker = str(metadata.get('speaker') or '').strip()
        if not speaker:
            raise ValueError('Episodic memories require a confirmed speaker profile.')
        metadata['speaker'] = speaker
        metadata.setdefault('source', 'conversation')
        metadata['added'] = datetime.now().astimezone().isoformat(timespec='seconds')
        if self.store:
            profile_id = self.store.profile_id(speaker)
            if not profile_id:
                raise ValueError('Episodic memories require a matched profile.')
            self.store.save_memory(text, 'episode', profile_id=profile_id, metadata=metadata,
                                   embedding=self.embed(text), source='conversation')
            return
        self.episodic.upsert(embeddings=[self.embed(text)], documents=[text], metadatas=[metadata],
                             ids=[f"epi_{uuid.uuid4().hex}"])

    def add_preference(self, key, value):
        text = f"{key}: {value}"
        metadata = {'key': key, 'value': value, 'scope': 'shared', 'added': datetime.now().astimezone().isoformat(timespec='seconds')}
        if self.store:
            self.store.save_preference(str(key), value, shared=True, source='explicit')
            self.store.save_memory(text, 'preference', shared=True, metadata=metadata,
                                   embedding=self.embed(text), source='explicit', memory_id=f'preference:{key}')
            return
        self.preferences.upsert(embeddings=[self.embed(text)], documents=[text], metadatas=[metadata], ids=[f"pref_{key}"])

    def recall(self, query, collection='semantic', limit=3, speaker=None, scope=None):
        if limit <= 0:
            return []
        if self.store:
            kind_map = {'semantic': ('note','idea','semantic','knowledge'),
                        'episodic': ('episode',), 'preferences': ('preference',)}
            kinds = kind_map.get(collection)
            if not kinds or (collection == 'episodic' and not speaker):
                return []
            profile_id = self.store.profile_id(speaker)
            query_vector = self.embed(query)
            if query_vector is not None:
                rows = self.store.search_memories(query_vector, profile_id=profile_id,
                                                  kinds=kinds, limit=limit)
            else:
                rows = []
            if not rows:
                rows = self.store.search_memories_text(query, profile_id=profile_id,
                                                       kinds=kinds, limit=limit)
            return [{'text': row['content'], 'metadata': row.get('metadata') or {}}
                    for row in rows]
        collection_map = {'semantic': self.semantic, 'episodic': self.episodic, 'preferences': self.preferences}
        target = collection_map.get(collection)
        if target is None:
            return []
        filters = {}
        if collection == 'episodic':
            if not speaker:
                return []
            filters['speaker'] = {'$eq': speaker}
        if scope:
            filters['scope'] = {'$eq': scope}
        results = target.query(query_embeddings=[self.embed(query)], n_results=limit, where=filters or None)
        memories = []
        documents = results.get('documents') or [[]]
        metadatas = results.get('metadatas') or [[]]
        if documents and documents[0]:
            for i, doc in enumerate(documents[0]):
                meta = metadatas[0][i] if i < len(metadatas[0]) and metadatas[0][i] else {}
                memories.append({'text': doc, 'metadata': meta})
        return memories

    def get_all_preferences(self):
        if self.store:
            return self.store.load_preferences()
        result = self.preferences.get()
        if result.get('documents'):
            prefs = {}
            for i, doc in enumerate(result['documents']):
                meta = result['metadatas'][i] if result.get('metadatas') else {}
                prefs[meta.get('key', '')] = meta.get('value', '')
            return prefs
        return {}

    def search_conversations(self, query, limit=3, speaker=None):
        if not speaker:
            return []
        return self.recall(query, 'episodic', limit, speaker=speaker)

    def search_knowledge(self, query, limit=3):
        return self.recall(query, 'semantic', limit, scope='shared')