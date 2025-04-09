import re
import random
import asyncio
from typing import Dict, Optional, List

import requests
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Record
from astrbot.core.platform import AstrMessageEvent
from pathlib import Path
from astrbot.api.provider import LLMResponse

# 常量定义
PLUGIN_NAME = "astrbot_plugin_GPT_SoVITS"
PLUGIN_AUTHOR = "Zhalslar"
PLUGIN_DESCRIPTION = "GPT_SoVITS对接插件"
PLUGIN_VERSION = "1.4.1"

# 目录配置
SAVED_AUDIO_DIR = Path("./data/plugins_data/astrbot_plugin_GPT_SoVITS")
SAVED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 锁机制相关变量
qqbot_lock = asyncio.Lock()
qqbot_processing = False

@register(PLUGIN_NAME, PLUGIN_AUTHOR, PLUGIN_DESCRIPTION, PLUGIN_VERSION)
class GPTSoVITSPlugin(Star):
    """GPT-SoVITS插件主类
    
    用于将文本转换为语音，支持多个模型和随机模型选择。
    支持通过命令触发和自动触发两种方式。
    """
    
    def __init__(self, context: Context, config: AstrBotConfig):
        """初始化插件
        
        Args:
            context: 插件上下文
            config: 插件配置
        """
        super().__init__(context)
        self.config = config
        self._init_config(config)
        
    def _init_config(self, config: AstrBotConfig) -> None:
        """初始化配置
        
        Args:
            config: 插件配置对象
        """
        # 基础设置
        base_setting = config.get('base_setting', {})
        self.base_url: str = base_setting.get('base_url', 'http://127.0.0.1:9880')
        
        # 自动配置
        auto_config: Dict = config.get('auto_config', {})
        self.send_record_probability: float = auto_config.get("send_record_probability", 0.15)
        self.max_resp_text_len: int = auto_config.get("max_resp_text_len", 50)
        self.random_model: bool = auto_config.get("random_model", False)
        
        # TTS参数
        self.default_params = {
            "text": "",
            "text_language": config.get('text_language', "zh"),
            "model_name": config.get('model_name', "ruoruo")
        }
        
        # 模型列表
        self.model_list: List[str] = config.get('model_list', ["ruoruo"])
        
        # 模型名称映射（硬编码）
        self.model_mapping: Dict[str, str] = {
            "若若": "ruoruo",
            "步非烟": "bufeiyan",
            "欣小萌": "xinxiaomeng",
            "杨幂": "yangmi"
        }


    def _get_model_name(self, input_name: str) -> str:
        """获取实际的模型名称
        
        Args:
            input_name: 输入的模型名称
            
        Returns:
            str: 实际的模型名称
        """
        return self.model_mapping.get(input_name, input_name)

    async def _generate_audio(self, text: str, event: AstrMessageEvent) -> Optional[str]:
        """生成语音文件
        
        Args:
            text: 要转换的文本
            event: 消息事件对象
            
        Returns:
            Optional[str]: 生成的音频文件路径，失败返回None
        """
        if not text:
            return None
            
        # 只保留中文、英文、逗号、句号和感叹号
        filtered_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z,。!]', '', text)
        if not filtered_text:
            return None
            
        params = {
            "text": filtered_text,
            "text_language": self.default_params["text_language"],
            "model_name": self.default_params["model_name"]
        }
        
        # 只有在没有指定模型的情况下才随机选择
        if self.random_model and self.model_list and params["model_name"] == self.default_params["model_name"]:
            model_name = random.choice(self.model_list)
            logger.info(f"随机选择模型: {model_name}")
            params["model_name"] = model_name
            
        file_name = self._generate_file_name(event, filtered_text)
        return await self._tts_inference(params, file_name)

    def _generate_file_name(self, event: AstrMessageEvent, text: str) -> str:
        """生成音频文件名
        
        Args:
            event: 消息事件对象
            text: 文本内容
            
        Returns:
            str: 生成的文件名
        """
        group_id = event.get_group_id() or '0'
        sender_id = event.get_sender_id() or '0'
        sanitized_text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\s]', '', text)
        limit_text = sanitized_text.strip()[:30]
        return f"{group_id}_{sender_id}_{limit_text}.wav"

    async def _tts_inference(self, params: Dict, file_name: str) -> Optional[str]:
        """调用TTS服务生成语音
        
        Args:
            params: TTS参数
            file_name: 保存的文件名
            
        Returns:
            Optional[str]: 生成的音频文件路径，失败返回None
        """
        try:
            # 发送请求到后端
            response = requests.post(self.base_url, json=params)
            response.raise_for_status()
            
            # 保存音频文件
            save_path = str(SAVED_AUDIO_DIR / file_name)
            with open(save_path, 'wb') as audio_file:
                audio_file.write(response.content)
            return save_path
            
        except requests.RequestException as e:
            logger.error(f"TTS请求失败: {e}")
            return None
        except IOError as e:
            logger.error(f"音频文件保存失败: {e}")
            return None
        except Exception as e:
            logger.error(f"TTS处理过程出错: {e}")
            return None

    @filter.on_decorating_result()
    async def on_llm_response(self, event: AstrMessageEvent) -> None:
        """处理LLM响应，自动将文本转换为语音
        
        Args:
            event: 消息事件对象
        """
        if random.random() > self.send_record_probability:
            return

        chain = event.get_result().chain
        if not (len(chain) == 1 and chain[0].type == 'Plain'):
            return

        text = chain[0].text
        if len(text) > self.max_resp_text_len:
            return

        save_path = await self._generate_audio(text, event)
        if save_path:
            chain.clear()
            chain.append(Record.fromFileSystem(save_path))

    @filter.regex(r"^(.+?)\s*(.+)")
    async def on_say(self, event: AstrMessageEvent) -> None:
        """处理语音转换命令
        
        Args:
            event: 消息事件对象
        """
        message = event.get_message_str()
        prefix = self.config.get('base_setting', {}).get('command_prefix', '说')
        if not message.startswith(prefix):
            return
            
        text = message[len(prefix):].strip()
        
        save_path = await self._generate_audio(text, event)
        if save_path:
            chain = [Record.fromFileSystem(save_path)]
            yield event.chain_result(chain)

    @filter.regex(r"^(.+?)说\s*(.+)")
    async def on_say_with_model(self, event: AstrMessageEvent) -> None:
        """处理"XXX说XXX"命令，使用指定的模型
        
        Args:
            event: 消息事件对象
        """
        message = event.get_message_str()
        model_name, text = message.split("说", 1)
        model_name = model_name.strip()
        text = text.strip()
        
        # 获取实际的模型名称
        actual_model = self._get_model_name(model_name)
        logger.info(f"将模型名称 '{model_name}' 映射为 '{actual_model}'")
        
        # 保存当前模型名称
        original_model = self.default_params["model_name"]
        
        try:
            # 临时设置新的模型名称
            self.default_params["model_name"] = actual_model
            logger.info(f"使用模型 {actual_model} 生成语音")
            
            save_path = await self._generate_audio(text, event)
            if save_path:
                chain = [Record.fromFileSystem(save_path)]
                yield event.chain_result(chain)
        finally:
            # 恢复原来的模型名称
            self.default_params["model_name"] = original_model

    @filter.command("重启TTS", alias={"重启tts"})
    async def tts_control(self, event: AstrMessageEvent) -> None:
        """重启TTS服务
        
        Args:
            event: 消息事件对象
        """
        yield event.plain_result("重启TTS中...(报错信息请忽略，等待一会即可完成重启)")
        
        try:
            endpoint = f"{self.base_url}/control"
            response = requests.get(endpoint, params={"command": "restart"})
            response.raise_for_status()
            logger.info("TTS服务重启成功")
        except requests.RequestException as e:
            logger.error(f"TTS服务重启失败: {e}")
        except Exception as e:
            logger.error(f"TTS服务重启出错: {e}")

    @filter.command("TTSmodel", alias={"TTS模型"})
    async def show_models(self, event: AstrMessageEvent) -> None:
        """展示当前可用的模型列表，支持切换模型
        
        Args:
            event: 消息事件对象
        """
        message = event.get_message_str().strip()
        parts = message.split(maxsplit=1)
        
        # 如果只输入了命令，显示模型列表
        if len(parts) == 1:
            if not self.model_list:
                yield event.plain_result("当前没有配置任何模型")
                return
                
            model_info = "下面列出了此服务提供商可用模型:\n"
            for i, model in enumerate(self.model_list, 1):
                model_info += f"{i}. {model}\n"
                
            current_model = self.default_params["model_name"]
            model_info += f"当前模型: [{current_model}]\n"
            model_info += "Tips: 使用 /TTSmodel <模型名/编号>，即可实时更换模型。如目标模型不存在于上表，请输入模型名。"
            
            yield event.plain_result(model_info)
            return
            
        # 处理模型切换
        target_model = parts[1].strip()
        try:
            # 尝试通过编号切换
            model_index = int(target_model) - 1
            if 0 <= model_index < len(self.model_list):
                new_model = self.model_list[model_index]
            else:
                yield event.plain_result(f"错误：模型编号 {target_model} 不存在")
                return
        except ValueError:
            # 通过模型名切换
            new_model = target_model
            
        # 更新默认模型
        self.default_params["model_name"] = new_model
        yield event.plain_result(f"已切换到模型: [{new_model}]")





