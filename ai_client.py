# -*- coding: utf-8 -*-
"""
AI 客户端模块 - 支持多种 AI 服务
"""
import os
import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Generator

DATABASE = 'novels.db'

OPENAI_TEXT_MODEL_PREFIXES = ('gpt-', 'o1', 'o3', 'o4', 'chatgpt-')
COMMON_EXCLUDED_MODEL_KEYWORDS = (
    'embedding', 'rerank', 'moderation', 'whisper',
    'tts', 'dall-e', 'transcribe', 'speech-to-text'
)


def _normalize_model_list(models: List[str], *, provider: str = '') -> List[str]:
    """清洗并去重模型列表。"""
    normalized = []
    seen = set()

    for model in models or []:
        if not isinstance(model, str):
            continue

        model_name = model.strip()
        if model_name.lower().startswith('models/'):
            model_name = model_name.split('/', 1)[1]
        if not model_name:
            continue

        lowered = model_name.lower()
        if any(keyword in lowered for keyword in COMMON_EXCLUDED_MODEL_KEYWORDS):
            continue

        if provider == 'gemini' and any(keyword in lowered for keyword in ('image', 'audio', 'computer-use', 'robotics')):
            continue

        if provider == 'openai' and not lowered.startswith(OPENAI_TEXT_MODEL_PREFIXES):
            continue

        if provider == 'claude' and not lowered.startswith('claude'):
            continue

        if provider == 'gemini' and 'gemini' not in lowered:
            continue

        if lowered in seen:
            continue

        seen.add(lowered)
        normalized.append(model_name)

    return sorted(normalized, key=str.lower)


def _extract_openai_style_models(payload: Dict[str, Any]) -> List[str]:
    """从 OpenAI 兼容接口响应中提取模型名。"""
    models = []
    for item in payload.get('data', []) or []:
        if isinstance(item, dict):
            model_name = item.get('id') or item.get('name')
            if model_name:
                models.append(model_name)
    return models


def _get_provider_defaults(provider: str) -> List[str]:
    """获取提供商默认模型，用于发现失败时回退。"""
    for item in AIClientFactory.get_available_providers():
        if item.get('id') == provider:
            return item.get('models', [])
    return []


def _discover_openai_models(config: Dict[str, Any]) -> List[str]:
    import requests

    api_base = (config.get('api_base') or 'https://api.openai.com/v1/').rstrip('/') + '/'
    response = requests.get(
        f'{api_base}models',
        headers={'Authorization': f"Bearer {config.get('api_key', '')}"},
        timeout=(10, 30)
    )
    response.raise_for_status()
    return _normalize_model_list(_extract_openai_style_models(response.json()), provider='openai')


def _discover_openai_compatible_models(config: Dict[str, Any]) -> List[str]:
    import requests

    api_base = (config.get('api_base') or 'https://api.openai.com/v1/').rstrip('/') + '/'
    response = requests.get(
        f'{api_base}models',
        headers={'Authorization': f"Bearer {config.get('api_key', '')}"},
        timeout=(10, 30)
    )
    response.raise_for_status()
    return _normalize_model_list(_extract_openai_style_models(response.json()), provider='openai-compatible')


def _discover_gemini_models(config: Dict[str, Any]) -> List[str]:
    import requests

    api_base = (config.get('api_base') or GeminiClient.DEFAULT_BASE_URL).rstrip('/') + '/'

    try:
        response = requests.get(
            f'{api_base}models',
            headers={'Authorization': f"Bearer {config.get('api_key', '')}"},
            timeout=(10, 30)
        )
        response.raise_for_status()
        models = _normalize_model_list(_extract_openai_style_models(response.json()), provider='gemini')
        if models:
            return models
    except Exception:
        pass

    response = requests.get(
        'https://generativelanguage.googleapis.com/v1beta/models',
        params={'key': config.get('api_key', '')},
        timeout=(10, 30)
    )
    response.raise_for_status()

    model_names = []
    for item in response.json().get('models', []) or []:
        if not isinstance(item, dict):
            continue
        supported_methods = item.get('supportedGenerationMethods') or []
        if supported_methods and not any('generateContent' in method for method in supported_methods):
            continue
        model_name = (item.get('name') or '').split('/')[-1]
        if model_name:
            model_names.append(model_name)

    return _normalize_model_list(model_names, provider='gemini')


def _discover_claude_models(config: Dict[str, Any]) -> List[str]:
    import requests

    api_base = (config.get('api_base') or 'https://api.anthropic.com/v1/').rstrip('/') + '/'
    response = requests.get(
        f'{api_base}models',
        headers={
            'x-api-key': config.get('api_key', ''),
            'anthropic-version': '2023-06-01'
        },
        timeout=(10, 30)
    )
    response.raise_for_status()

    models = []
    for item in response.json().get('data', []) or []:
        if isinstance(item, dict) and item.get('id'):
            models.append(item['id'])

    return _normalize_model_list(models, provider='claude')


def _discover_ollama_models(config: Dict[str, Any]) -> List[str]:
    import requests

    api_base = (config.get('api_base') or 'http://localhost:11434').rstrip('/')
    response = requests.get(f'{api_base}/api/tags', timeout=(5, 15))
    response.raise_for_status()

    models = []
    for item in response.json().get('models', []) or []:
        if isinstance(item, dict):
            model_name = item.get('name') or item.get('model')
            if model_name:
                models.append(model_name)

    return _normalize_model_list(models, provider='ollama')


class AIConfig:
    """AI 配置管理"""

    @staticmethod
    def get_db():
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_table():
        """初始化 AI 配置表"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'openai',
                api_key TEXT,
                api_base TEXT,
                model TEXT DEFAULT 'gpt-3.5-turbo',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 2000,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 插入默认配置
        cursor.execute('''
            INSERT OR IGNORE INTO ai_configs (id, name, provider, model, is_active)
            VALUES (1, '默认配置', 'openai', 'gpt-3.5-turbo', 0)
        ''')

        conn.commit()
        conn.close()

    @staticmethod
    def get_active_config() -> Optional[Dict[str, Any]]:
        """获取当前激活的配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ai_configs WHERE is_active = 1 LIMIT 1')
        config = cursor.fetchone()

        conn.close()

        if config:
            return dict(config)
        return None

    @staticmethod
    def get_all_configs() -> List[Dict[str, Any]]:
        """获取所有配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ai_configs ORDER BY created_at DESC')
        configs = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return configs

    @staticmethod
    def get_config(config_id: int) -> Optional[Dict[str, Any]]:
        """获取指定配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ai_configs WHERE id = ?', (config_id,))
        config = cursor.fetchone()

        conn.close()

        if config:
            return dict(config)
        return None

    @staticmethod
    def save_config(config_data: Dict[str, Any]) -> int:
        """????"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        config_id = config_data.get('id')

        if config_id:
            existing_config = AIConfig.get_config(config_id) or {}
            api_key = config_data.get('api_key')
            if api_key is None or (isinstance(api_key, str) and (not api_key.strip() or api_key.startswith('***'))):
                api_key = existing_config.get('api_key')

            # ??????
            cursor.execute('''
                UPDATE ai_configs SET
                    name = ?,
                    provider = ?,
                    api_key = ?,
                    api_base = ?,
                    model = ?,
                    temperature = ?,
                    max_tokens = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                config_data.get('name'),
                config_data.get('provider', 'openai'),
                api_key,
                config_data.get('api_base'),
                config_data.get('model', 'gpt-3.5-turbo'),
                config_data.get('temperature', 0.7),
                config_data.get('max_tokens', 2000),
                config_id
            ))
        else:
            # ?????
            cursor.execute('''
                INSERT INTO ai_configs
                (name, provider, api_key, api_base, model, temperature, max_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_data.get('name'),
                config_data.get('provider', 'openai'),
                config_data.get('api_key'),
                config_data.get('api_base'),
                config_data.get('model', 'gpt-3.5-turbo'),
                config_data.get('temperature', 0.7),
                config_data.get('max_tokens', 2000)
            ))
            config_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return config_id


    @staticmethod
    def delete_config(config_id: int) -> bool:
        """删除配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM ai_configs WHERE id = ?', (config_id,))

        conn.commit()
        conn.close()

        return True

    @staticmethod
    def set_active_config(config_id: int) -> bool:
        """设置激活的配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        # 先取消所有激活状态
        cursor.execute('UPDATE ai_configs SET is_active = 0')

        # 设置指定配置为激活
        cursor.execute('UPDATE ai_configs SET is_active = 1 WHERE id = ?', (config_id,))

        conn.commit()
        conn.close()

        return True


class BaseAIClient(ABC):
    """AI 客户端基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get('api_key', '')
        self.api_base = config.get('api_base')
        self.model = config.get('model', 'gpt-3.5-turbo')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        """发送聊天请求"""
        pass

    @abstractmethod
    def test_connection(self) -> tuple:
        """测试连接，返回 (success, message)"""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI 客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        try:
            from openai import OpenAI

            client_kwargs = {
                'api_key': self.api_key,
            }

            if self.api_base:
                client_kwargs['base_url'] = self.api_base

            self.client = OpenAI(**client_kwargs)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """发送聊天请求"""
        if not self.client:
            raise RuntimeError("OpenAI 客户端未初始化")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=stream
        )

        if stream:
            return response
        else:
            return response.choices[0].message.content

    def test_connection(self) -> tuple:
        """测试连接"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True, "连接成功"
        except Exception as e:
            return False, str(e)


class ClaudeClient(BaseAIClient):
    """Claude 客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 Claude 客户端"""
        try:
            import anthropic

            client_kwargs = {
                'api_key': self.api_key,
            }

            if self.api_base:
                client_kwargs['base_url'] = self.api_base

            self.client = anthropic.Anthropic(**client_kwargs)
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """发送聊天请求"""
        if not self.client:
            raise RuntimeError("Claude 客户端未初始化")

        # 转换消息格式
        system_msg = ""
        chat_messages = []

        for msg in messages:
            if msg.get('role') == 'system':
                system_msg = msg.get('content', '')
            else:
                chat_messages.append({
                    "role": msg.get('role'),
                    "content": msg.get('content', '')
                })

        kwargs = {
            'model': self.model,
            'messages': chat_messages,
            'max_tokens': self.max_tokens,
        }

        if system_msg:
            kwargs['system'] = system_msg

        if stream:
            kwargs['stream'] = True
            return self.client.messages.create(**kwargs)
        else:
            response = self.client.messages.create(**kwargs)
            return response.content[0].text

    def test_connection(self) -> tuple:
        """测试连接"""
        try:
            response = self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True, "连接成功"
        except Exception as e:
            return False, str(e)


class OllamaClient(BaseAIClient):
    """Ollama 本地模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base = config.get('api_base', 'http://localhost:11434')

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """发送聊天请求"""
        import requests

        url = f"{self.api_base}/api/chat"

        data = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
            }
        }

        if stream:
            response = requests.post(url, json=data, stream=True)
            return response.iter_lines()
        else:
            response = requests.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            return result.get('message', {}).get('content', '')

    def test_connection(self) -> tuple:
        """测试连接"""
        try:
            import requests
            response = requests.get(f"{self.api_base}/api/tags", timeout=5)
            if response.status_code == 200:
                return True, "连接成功"
            return False, f"状态码: {response.status_code}"
        except Exception as e:
            return False, str(e)


class GeminiClient(BaseAIClient):
    """Google Gemini ?????? Google AI Studio OpenAI ?????"""

    DEFAULT_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base = (self.api_base or self.DEFAULT_BASE_URL).rstrip('/') + '/'

    def _request_chat_completions(self, messages: List[Dict[str, str]], stream: bool = False):
        import requests

        url = f"{self.api_base}chat/completions"
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'stream': stream,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        response = requests.post(url, headers=headers, json=payload, stream=stream, timeout=(10, 60))
        response.raise_for_status()
        return response

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """??????"""
        response = self._request_chat_completions(messages, stream=stream)

        if stream:
            def generate() -> Generator[str, None, None]:
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith('data: '):
                        payload = line[6:].strip()
                        if payload == '[DONE]':
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get('choices') or []
                        if not choices:
                            continue
                        delta = choices[0].get('delta') or {}
                        content = delta.get('content')
                        if content:
                            yield content
            return generate()

        result = response.json()
        choices = result.get('choices') or []
        if not choices:
            return ''
        message = choices[0].get('message') or {}
        return message.get('content', '')

    def test_connection(self) -> tuple:
        """测试连接"""
        import requests

        original_max_tokens = self.max_tokens
        try:
            self.max_tokens = min(max(int(self.max_tokens or 32), 8), 64)
            response = self._request_chat_completions(
                [{'role': 'user', 'content': 'Hello'}],
                stream=False,
            )
            result = response.json()
            choices = result.get('choices') or []
            if choices:
                return True, '连接成功'
            return False, '接口已响应，但未返回可用内容'
        except requests.HTTPError as exc:
            try:
                error_data = exc.response.json()
                return False, json.dumps(error_data, ensure_ascii=False)
            except Exception:
                return False, exc.response.text or str(exc)
        except Exception as exc:
            error_msg = str(exc)
            if 'failed to connect' in error_msg.lower() or 'timeout' in error_msg.lower():
                return False, '连接失败：无法访问 Google AI Studio 接口，请检查网络或代理设置。'
            return False, error_msg
        finally:
            self.max_tokens = original_max_tokens


class OpenAICompatibleClient(BaseAIClient):
    """OpenAI ?? API ????? DashScope????Google AI Studio ??"""

    DEFAULT_BASE_URL = 'https://api.openai.com/v1/'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base = (self.api_base or self.DEFAULT_BASE_URL).rstrip('/') + '/'

    def _request_chat_completions(self, messages: List[Dict[str, str]], stream: bool = False):
        import requests

        url = f"{self.api_base}chat/completions"
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'stream': stream,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        response = requests.post(url, headers=headers, json=payload, stream=stream, timeout=(10, 60))
        response.raise_for_status()
        return response

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """??????"""
        response = self._request_chat_completions(messages, stream=stream)

        if stream:
            def generate() -> Generator[str, None, None]:
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith('data: '):
                        payload = line[6:].strip()
                        if payload == '[DONE]':
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get('choices') or []
                        if not choices:
                            continue
                        delta = choices[0].get('delta') or {}
                        content = delta.get('content')
                        if content:
                            yield content
            return generate()

        result = response.json()
        choices = result.get('choices') or []
        if not choices:
            return ''
        message = choices[0].get('message') or {}
        return message.get('content', '')

    def test_connection(self) -> tuple:
        """测试连接"""
        import requests

        original_max_tokens = self.max_tokens
        try:
            self.max_tokens = min(max(int(self.max_tokens or 32), 8), 64)
            response = self._request_chat_completions(
                [{'role': 'user', 'content': 'Hello'}],
                stream=False,
            )
            result = response.json()
            choices = result.get('choices') or []
            if choices:
                return True, '连接成功'
            return False, '接口已响应，但未返回可用内容'
        except requests.HTTPError as exc:
            try:
                error_data = exc.response.json()
                return False, json.dumps(error_data, ensure_ascii=False)
            except Exception:
                return False, exc.response.text or str(exc)
        except Exception as exc:
            return False, str(exc)


class AIClientFactory:
    """AI 客户端工厂"""

    PROVIDERS = {
        'openai': OpenAIClient,
        'claude': ClaudeClient,
        'ollama': OllamaClient,
        'gemini': GeminiClient,
        'openai-compatible': OpenAICompatibleClient,
    }

    @classmethod
    def create_client(cls, config: Dict[str, Any]) -> BaseAIClient:
        """创建 AI 客户端"""
        provider = config.get('provider', 'openai')
        client_class = cls.PROVIDERS.get(provider)

        if not client_class:
            raise ValueError(f"不支持的 AI 提供商: {provider}")

        return client_class(config)

    @classmethod
    def discover_models(cls, config: Dict[str, Any]) -> List[str]:
        """根据配置发现当前接口可用模型。"""
        provider = config.get('provider', 'openai')

        try:
            if provider == 'openai':
                models = _discover_openai_models(config)
            elif provider == 'openai-compatible':
                models = _discover_openai_compatible_models(config)
            elif provider == 'gemini':
                models = _discover_gemini_models(config)
            elif provider == 'claude':
                models = _discover_claude_models(config)
            elif provider == 'ollama':
                models = _discover_ollama_models(config)
            else:
                models = []
        except Exception:
            models = []

        if not models:
            return _get_provider_defaults(provider)
        return models

    @classmethod
    def get_available_providers(cls) -> List[Dict[str, str]]:
        """获取可用的 AI 提供商列表"""
        return [
            {'id': 'openai', 'name': 'OpenAI', 'models': ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o']},
            {'id': 'openai-compatible', 'name': 'OpenAI 兼容 API', 'models': ['qwen-turbo', 'qwen-plus', 'deepseek-chat', 'moonshot-v1-8k', 'gemini-2.5-flash', 'gemini-3-pro-preview']},
            {'id': 'claude', 'name': 'Claude (Anthropic)', 'models': ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']},
            {'id': 'gemini', 'name': 'Google Gemini', 'models': ['gemini-2.5-flash', 'gemini-3-pro-preview', 'gemini-2.0-flash']},
            {'id': 'ollama', 'name': 'Ollama (本地)', 'models': ['llama2', 'llama3', 'mistral', 'qwen', 'phi3']},
        ]


def get_ai_client() -> Optional[BaseAIClient]:
    """获取当前配置的 AI 客户端"""
    config = AIConfig.get_active_config()

    if not config:
        return None

    # 检查是否需要 API Key
    provider = config.get('provider', 'openai')
    requires_api_key = provider not in ['ollama']  # Ollama 不需要 API Key

    if requires_api_key and not config.get('api_key'):
        return None

    try:
        return AIClientFactory.create_client(config)
    except Exception as e:
        print(f"创建 AI 客户端失败: {e}")
        return None


# 初始化数据库表
AIConfig.init_table()
