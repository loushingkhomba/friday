import os
import ntpath
import subprocess
import requests
import json
import re
import hashlib
import pyautogui
from bs4 import BeautifulSoup
from datetime import datetime
import ollama
import xml.etree.ElementTree as ET

class BaseAgent:
    def __init__(self, assistant):
        self.assistant = assistant

    def execute(self, params):
        raise NotImplementedError('Subclasses must implement execute()')

class PlannerAgent(BaseAgent):
    """The Strategist: Decomposes complex goals into a sequence of agent tasks."""
    def execute(self, goal):
        try:
            system_prompt = (
                "You are the Strategic Planner for Friday AI. Your job is to break down a user goal into a sequence of actionable steps. "
                "Available Agents: MEMORY (search notes only), WEB (online lookup only when enabled), "
                "SYSTEM (only when planner system actions are enabled by the user's guardrails). "
                "Return ONLY a JSON list of 1 to 5 steps. Each step must contain exactly 'agent' and 'params'; "
                "agent must be MEMORY, WEB, or SYSTEM; params must be a short string under 500 characters. "
                "Do not create or save notes as a side effect of planning. The user can ask Friday directly to save a note.\n"
                "Example: 'Find my note about AI' -> [{\"agent\": \"MEMORY\", \"params\": \"find note AI\"}]"
            )
            model, reason = self.assistant.select_chat_model(goal)
            self.assistant.logger.info('model router selected=%s reason=%s task=planner', model, reason)
            response, _ = self.assistant.chat_model_with_fallback([
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': goal}
            ], max_tokens=384, model=model)
            content = response['message']['content'].strip()
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

class CorrectionAgent(BaseAgent):
    """The Critic: Analyzes failures and suggests corrected parameters."""
    def execute(self, failure_data):
        # failure_data should be a dict: {"goal": ..., "params": ..., "error": ...}
        try:
            system_prompt = (
                "You are the Quality Assurance agent for Friday AI. A task has failed. "
                "Your job is to analyze the failure and provide a BETTER set of parameters to succeed. "
                "Return ONLY a JSON object with 'corrected_params' and 'reasoning'.\n"
                "Example failure: Search for 'the blue folder' returned nothing. "
                "Corrected params: 'blue folder' (removing 'the')."
            )
            prompt = f"Goal: {failure_data.get('goal')}\nAttempted Params: {failure_data.get('params')}\nError/Result: {failure_data.get('error')}"
            response = self.assistant.chat_model([
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ], max_tokens=256)
            content = response['message']['content'].strip()
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()
            return json.loads(content)
        except Exception as e:
            return {"error": str(e), "corrected_params": None}

class MemoryAgent(BaseAgent):
    """Handles note retrieval and storage."""
    def execute(self, params):
        query = " ".join(params) if isinstance(params, list) else str(params)
        if not query:
            return {"status": "error", "message": "I need a specific query."}

        low_query = query.lower()
        if any(word in low_query for word in ["save note", "save idea", "create note", "add to notes"]):
            content = query
            for word in ["save note", "save idea", "create note", "add to notes"]:
                content = content.replace(word, "").strip(": ")
            return self.save_memory(content)

        search_term = low_query
        for word in ["find", "search", "out", "my", "notes", "memories", "check", "friday"]:
            search_term = search_term.replace(word, "").strip()
        
        if not search_term:
            all_notes = [n["text"] for n in self.assistant.data["notes"]] + [i["text"] for i in self.assistant.data["ideas"]]
            if not all_notes:
                return {"status": "empty", "results": []}
            return {"status": "success", "results": all_notes[-5:]}

        notes_matches = [n["text"] for n in self.assistant.data["notes"] if search_term in n["text"].lower()]
        idea_matches = [i["text"] for i in self.assistant.data["ideas"] if search_term in i["text"].lower()]
        results = notes_matches + idea_matches
        
        if self.assistant.memory:
            try:
                memories = self.assistant.memory.search_knowledge(search_term, limit=2)
                if memories:
                    results.extend([m['text'] for m in memories])
            except Exception:
                self.assistant.logger.exception('could not retrieve shared semantic memories')

        if not results:
            return {"status": "not_found", "query": search_term}
        
        return {"status": "success", "results": results[:5]}

    def save_memory(self, text):
        is_idea = "idea" in text.lower()
        timestamp = datetime.now().isoformat(timespec='microseconds')
        if is_idea:
            entry = {'id': max((item.get('id', 0) for item in self.assistant.data['ideas']
                                if isinstance(item, dict) and isinstance(item.get('id', 0), int)), default=0) + 1,
                     'text': text, 'timestamp': timestamp}
            self.assistant.data['ideas'].append(entry)
            self.assistant.data['last_undo_action'] = {'kind': 'idea', 'id': entry['id'], 'timestamp': timestamp}
        else:
            entry = {'id': max((item.get('id', 0) for item in self.assistant.data['notes']
                                if isinstance(item, dict) and isinstance(item.get('id', 0), int)), default=0) + 1,
                     'text': text, 'category': 'General', 'timestamp': timestamp}
            self.assistant.data['notes'].append(entry)
            self.assistant.data['last_undo_action'] = {'kind': 'note', 'id': entry['id'], 'timestamp': timestamp}
        self.assistant.save_data()
        if self.assistant.memory:
            try:
                self.assistant.memory.add_semantic(text, {
                    'source': 'user_saved_idea' if is_idea else 'user_saved_note',
                    'kind': 'idea' if is_idea else 'note',
                    'scope': 'shared',
                })
            except Exception:
                # data.json remains the source of truth; Chroma is a searchable index.
                self.assistant.logger.exception('saved note to data.json but failed to index it in ChromaDB')
        return {"status": "success", "results": [f"Successfully saved: {text}"]}

class WebAgent(BaseAgent):
    """Handles optional online lookups; disabled by default in offline mode."""
    def execute(self, params):
        query = ' '.join(params) if isinstance(params, list) else str(params)
        if not query:
            return 'What would you like me to look up?'

        if self.assistant.offline_mode:
            if 'weather' in query.lower():
                return 'Live weather needs internet access. I can answer general weather questions from local model knowledge.'
            if 'news' in query.lower() or 'headline' in query.lower() or 'event' in query.lower():
                return 'Live news and event lookup needs internet access. Friday is in offline mode.'
            return 'Online lookup is disabled in offline mode. I can answer general questions from local model knowledge.'

        if 'weather' in query.lower():
            return self.get_weather(query)
        elif 'news' in query.lower():
            return self.get_news(query)
        elif 'wikipedia' in query.lower():
            return self.wikipedia_search(query)
        else:
            return self.web_search(query)

    def web_search(self, query):
        url = f'https://www.google.com/search?q={query.replace(" ", "+")}'
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('div', class_='BNeawe vvjwJb AP7Wnd')
            if results:
                return results[0].get_text()[:300]
            return f'No search result snippet was available for {query}.'
        except:
            return 'Web search is unavailable right now.'

    def wikipedia_search(self, query):
        topic = query.lower().replace('wikipedia', '').strip()
        url = f'https://en.wikipedia.org/wiki/{topic.replace(" ", "_")}'
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, timeout=5, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                p = soup.find('p')
                if p: return p.get_text()[:300]
        except:
            pass
        return f'I could not retrieve a Wikipedia summary for {topic}.'

    def get_weather(self, query):
        city_match = re.search(r'\b(?:in|for)\s+([a-z][a-z .\'-]*?)(?:[?.!,]|$)', query, re.IGNORECASE)
        city = city_match.group(1).strip() if city_match else self.assistant.get_user_city()
        city = re.sub(r'\s+(?:today|tomorrow|tonight)$', '', city, flags=re.IGNORECASE)
        try:
            geocode_url = 'https://geocoding-api.open-meteo.com/v1/search'
            geo_res = requests.get(geocode_url, params={'name': city, 'count': 1}, timeout=5).json()
            if geo_res.get('results'):
                lat, lon = geo_res['results'][0]['latitude'], geo_res['results'][0]['longitude']
                w_url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m'
                w_res = requests.get(w_url, timeout=5).json()
                temp = w_res['current']['temperature_2m']
                return f'The current temperature in {city} is {temp} degrees Celsius.'
        except:
            pass
        return 'Unable to fetch weather at the moment.'

    def get_news(self, query):
        # Google News RSS provides current headlines without opening a browser.
        city = self.assistant.get_user_city()
        topic = re.sub(
            r"\b(?:okay|alright|please|friday|can you|could you|tell me|show me|give me|"
            r"let's see|what(?:'s| is)?(?: going on)?|you got|some)\b", ' ', query.strip(), flags=re.IGNORECASE
        )
        topic = re.sub(r"\b(?:the|latest|recent|current|breaking|today'?s|today|some|news|headlines|updates)\b", ' ', topic, flags=re.IGNORECASE)
        topic = re.sub(r"\b(?:about|on|for|in)\b", ' ', topic, flags=re.IGNORECASE)
        topic = re.sub(r'\s+', ' ', topic).strip(' ,.!?')
        if not topic or topic.lower() in {'what', 'going on'}:
            topic = city
        elif re.search(r'\b(?:local|near me)\b', topic, re.IGNORECASE):
            topic = f'{topic} {city}'
        search_query = topic if re.search(r'\bnews\b', topic, re.IGNORECASE) else f'{topic} news'
        try:
            response = requests.get(
                'https://news.google.com/rss/search',
                params={'q': search_query, 'hl': 'en-IN', 'gl': 'IN', 'ceid': 'IN:en'},
                headers={'User-Agent': 'FridayPersonalAssistant/1.0'},
                timeout=(3, 6),
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            headlines = []
            for item in root.findall('.//item'):
                title = (item.findtext('title') or '').strip()
                source = (item.findtext('source') or '').strip()
                if title:
                    title = re.sub(r'\s+-\s+[^-]+$', '', title).strip()
                    headlines.append(f'{title}' + (f', from {source}' if source else ''))
                if len(headlines) == 3:
                    break
            if not headlines:
                return f'I couldnâ€™t find current headlines about {topic}. Try another topic.'
            return f'Latest headlines for {topic}, as of {datetime.now().strftime("%B %d, %I:%M %p")}: ' + '. '.join(headlines)
        except (requests.RequestException, ET.ParseError, ValueError) as error:
            self.assistant.logger.warning('live news lookup failed: %s', error)
            return 'I canâ€™t reach the live news feed right now. Please try again shortly.'

class SystemAgent(BaseAgent):
    """Handles OS and File system operations."""
    def execute(self, params):
        query = ' '.join(params) if isinstance(params, list) else str(params)
        route = query.lower()
        if re.search(r'\b(?:read|view)\s+(?:the\s+)?file\b', route):
            return self.read_file(query)
        elif re.search(r'\bappend\s+file\b', route):
            return self.append_file(query)
        elif re.search(r'\bwrite\s+file\b', route):
            return self.write_file(query)
        elif re.search(r'\b(?:search|find)\b.*\bfiles?\b', route):
            return self.search_files(query)
        elif 'volume' in route:
            return self.control_volume(route)
        elif 'open' in route:
            return self.open_app(route)
        elif 'close' in route:
            return self.close_app(route)
        return 'I cannot perform that system action.'

    def _safe_file_path(self, filename):
        """Resolve a relative file path and ensure it stays under Friday's root."""
        filename = filename.strip().strip('"').strip("'")
        if not filename or ntpath.isabs(filename) or ntpath.splitdrive(filename)[0]:
            raise ValueError('Use a relative path inside Fridayâ€™sFolder.')

        root = os.path.realpath(self.assistant.allowed_folder)
        candidate = os.path.realpath(os.path.join(root, filename))
        try:
            common = os.path.commonpath([root, candidate])
        except ValueError:
            raise ValueError('That path is outside Fridayâ€™sFolder.')
        if os.path.normcase(common) != os.path.normcase(root):
            raise ValueError('That path is outside Fridayâ€™sFolder.')
        return candidate

    def control_volume(self, query):
        if 'up' in query or 'increase' in query:
            for _ in range(5): pyautogui.press('volumeup')
            return 'Volume increased.'
        elif 'down' in query or 'decrease' in query:
            for _ in range(5): pyautogui.press('volumedown')
            return 'Volume decreased.'
        elif 'mute' in query:
            pyautogui.press('volumemute')
            return 'Volume muted.'
        return 'Volume command not recognized.'

    def open_app(self, query):
        blocked = self.assistant.guardrails.get('system', {}).get('blocked_apps', [])
        if any(str(app).lower() in query.lower() for app in blocked):
            return 'That app is blocked by Fridayâ€™s guardrails.'
        apps = {
            'chrome': 'chrome.exe', 
            'notepad': 'notepad.exe', 
            'calc': 'calc.exe', 
            'code': 'code', # VS Code
            'terminal': 'cmd', 
            'powershell': 'powershell', 
            'explorer': 'explorer',
            'word': 'winword',
            'excel': 'excel'
        }
        for key, exe in apps.items():
            if key in query:
                subprocess.Popen(exe)
                return f'Opening {key}.'
        return 'App not found in my map.'

    def close_app(self, query):
        apps = {'chrome': 'chrome.exe', 'notepad': 'notepad.exe'}
        for key, exe in apps.items():
            if key in query:
                subprocess.run(['taskkill', '/F', '/IM', exe], capture_output=True)
                return f'Closing {key}.'
        return 'Could not find app to close.'

    def read_file(self, query):
        match = re.search(r'\b(?:read|view)\s+(?:the\s+)?file\s+(.+?)\s*$', query, re.IGNORECASE)
        if not match: return 'Please specify a filename inside Fridayâ€™sFolder.'
        try:
            filename = match.group(1).strip()
            path = self._safe_file_path(filename)
            with open(path, 'r', encoding='utf-8') as f:
                return f'File content: {f.read()[:300]}'
        except Exception as e:
            return f'Error reading file: {e}'

    def write_file(self, query):
        try:
            # Expected format: "write file [relative name] content [text]"
            match = re.search(r'\bwrite\s+file\s+(.+?)\s+content(?:\s+(.*))?\s*$', query, re.IGNORECASE | re.DOTALL)
            if not match:
                return 'Please use the format: "write file [name] content [text]"'

            file_part, content_part = match.groups()
            content_part = content_part or ''
            path = self._safe_file_path(file_part)
            allow_overwrite = self.assistant.guardrails.get('filesystem', {}).get('allow_overwrite', False)
            mode = 'w' if allow_overwrite else 'x'
            with open(path, mode, encoding='utf-8') as f:
                f.write(content_part)
            if not allow_overwrite and hasattr(self.assistant, 'record_undo_action'):
                with open(path, 'rb') as f:
                    created_bytes = f.read()
                is_direct_child = os.path.dirname(path) == os.path.realpath(self.assistant.allowed_folder)
                action = ({
                    'kind': 'file_create', 'path': file_part, 'size': len(created_bytes),
                    'sha256': hashlib.sha256(created_bytes).hexdigest(),
                } if is_direct_child else {'kind': 'unsupported'})
                self.assistant.record_undo_action(action)
            elif allow_overwrite and hasattr(self.assistant, 'record_undo_action'):
                self.assistant.record_undo_action({'kind': 'unsupported'})
            self.assistant.last_file = file_part
            if hasattr(self.assistant, 'logger'):
                self.assistant.logger.info('file %s path=%s', 'written' if allow_overwrite else 'created', path)
            return f'Created {file_part} in Friday\'sFolder.' if not allow_overwrite else f'Updated {file_part} in Friday\'sFolder.'
        except FileExistsError:
            self.assistant.last_file = file_part
            return f'{file_part} already exists in Friday\'sFolder. I left it unchanged. Say "add" followed by your text, to that file, if you want to add content.'
        except Exception as e:
            return f'Error writing file: {e}'

    def append_file(self, query):
        try:
            match = re.search(r'\bappend\s+file\s+(.+?)\s+content(?:\s+(.*))?\s*$', query, re.IGNORECASE | re.DOTALL)
            if not match:
                return 'Tell me which file and what to add.'
            file_part, content_part = match.group(1).strip(), (match.group(2) or '').strip()
            if not content_part:
                return f'What should I add to {file_part}?'
            path = self._safe_file_path(file_part)
            if not os.path.isfile(path):
                return f"I can't find {file_part} in Friday'sFolder. Ask me to create it first."
            with open(path, 'rb') as f:
                original = f.read()
            try:
                original.decode('utf-8')
            except UnicodeDecodeError:
                return f"I can't append to {file_part}: it isn't a UTF-8 text file."
            separator = b'\n' if original and not original.endswith(b'\n') else b''
            addition = separator + content_part.encode('utf-8') + b'\n'
            updated = original + addition
            with open(path, 'ab') as f:
                f.write(addition)
            if hasattr(self.assistant, 'record_undo_action'):
                self.assistant.record_undo_action({
                    'kind': 'file_append', 'path': file_part, 'original_size': len(original),
                    'original_sha256': hashlib.sha256(original).hexdigest(),
                    'result_size': len(updated), 'result_sha256': hashlib.sha256(updated).hexdigest(),
                })
            self.assistant.last_file = file_part
            if hasattr(self.assistant, 'logger'):
                self.assistant.logger.info('file appended path=%s chars=%d', path, len(content_part))
            return f'Added that to {file_part}.'
        except Exception as e:
            return f'Error adding to file: {e}'

    def search_files(self, query):
        match = re.search(r'\b(?:search|find)\s+(?:for\s+)?(?:files?\s+)?(.+?)\s*$', query, re.IGNORECASE)
        q = match.group(1).strip().strip('"').strip("'") if match else ''
        if not q:
            return 'Tell me what filename to search for inside Fridayâ€™sFolder.'

        root = os.path.realpath(self.assistant.allowed_folder)
        files = []
        for current, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if os.path.commonpath(
                [root, os.path.realpath(os.path.join(current, name))]
            ) == root]
            for name in names:
                path = os.path.join(current, name)
                try:
                    safe_path = self._safe_file_path(os.path.relpath(path, root))
                except (ValueError, OSError):
                    continue
                if q.casefold() in name.casefold() and os.path.isfile(safe_path):
                    files.append(safe_path)
        if files:
            return f'Found {len(files)} files in Fridayâ€™sFolder. First one: {os.path.basename(files[0])}'
        return 'No files found.'
