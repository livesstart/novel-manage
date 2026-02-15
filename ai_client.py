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
        """保存配置"""
        conn = AIConfig.get_db()
        cursor = conn.cursor()

        config_id = config_data.get('id')

        if config_id:
            # 更新现有配置
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
                config_data.get('api_key'),
                config_data.get('api_base'),
                config_data.get('model', 'gpt-3.5-turbo'),
                config_data.get('temperature', 0.7),
                config_data.get('max_tokens', 2000),
                config_id
            ))
        else:
            # 插入新配置
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
    """Google Gemini 客户端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 Gemini 客户端"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            # 配置生成参数
            generation_config = {
                'temperature': self.temperature,
                'max_output_tokens': self.max_tokens,
            }

            self.client = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config
            )
        except ImportError:
            raise ImportError("请安装 google-generativeai: pip install google-generativeai")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """发送聊天请求"""
        if not self.client:
            raise RuntimeError("Gemini 客户端未初始化")

        # 转换消息格式为 Gemini 格式
        # Gemini 使用 history + current message 格式
        history = []
        current_message = None

        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')

            if role == 'system':
                # Gemini 不直接支持 system message，合并到第一条 user message
                if not history and not current_message:
                    current_message = f"System: {content}\n\n"
                continue
            elif role == 'user':
                if current_message is None:
                    current_message = content
                else:
                    history.append({'role': 'user', 'parts': [current_message]})
                    current_message = content
            elif role == 'assistant':
                history.append({'role': 'model', 'parts': [content]})

        if current_message is None:
            current_message = "Hello"

        # 创建聊天会话
        chat = self.client.start_chat(history=history)

        if stream:
            response = chat.send_message(current_message, stream=True)
            return response
        else:
            response = chat.send_message(current_message)
            return response.text

    def test_connection(self) -> tuple:
        """测试连接"""
        try:
            response = self.client.generate_content("Hello")
            return True, "连接成功"
        except Exception as e:
            return False, str(e)


class OpenAICompatibleClient(OpenAIClient):
    """OpenAI 兼容 API 客户端（如 DashScope、智谱、文心一言等）"""

    def __init__(self, config: Dict[str, Any]):
        # 调用父类初始化
        BaseAIClient.__init__(self, config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        try:
            from openai import OpenAI

            client_kwargs = {
                'api_key': self.api_key,
            }

            # 兼容 API 必须设置 base_url
            if self.api_base:
                client_kwargs['base_url'] = self.api_base
            else:
                # 使用常见的兼容地址作为默认
                client_kwargs['base_url'] = 'https://api.openai.com/v1'

            self.client = OpenAI(**client_kwargs)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        """发送聊天请求"""
        if not self.client:
            raise RuntimeError("OpenAI 兼容客户端未初始化")

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
    def get_available_providers(cls) -> List[Dict[str, str]]:
        """获取可用的 AI 提供商列表"""
        return [
            {'id': 'openai', 'name': 'OpenAI', 'models': ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o']},
            {'id': 'openai-compatible', 'name': 'OpenAI 兼容 API', 'models': ['qwen-turbo', 'qwen-plus', 'qwen-max', 'deepseek-chat', 'moonshot-v1-8k']},
            {'id': 'claude', 'name': 'Claude (Anthropic)', 'models': ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']},
            {'id': 'gemini', 'name': 'Google Gemini', 'models': ['gemini-pro', 'gemini-pro-vision', 'gemini-ultra']},
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
