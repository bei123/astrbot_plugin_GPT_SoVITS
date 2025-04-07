import re
import random

import requests
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Record
from astrbot.core.platform import AstrMessageEvent
from pathlib import Path
from typing import Dict
from astrbot.api.provider import LLMResponse

SAVED_AUDIO_DIR = Path("./data/plugins_data/astrbot_plugin_GPT_SoVITS")  # 语音文件保存目录

SAVED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@register("astrbot_plugin_GPT_SoVITS", "Zhalslar", "GPT_SoVITS对接插件", "1.1.3")
class GPTSoVITSPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        base_setting = config.get('base_setting')
        self.base_url: str = base_setting.get('base_url')

        auto_config: Dict = config.get('auto_config')
        self.send_record_probability: float = auto_config.get("send_record_probability")  # 发语音的概率
        self.max_resp_text_len: int = auto_config.get('max_resp_text_len')

        # 简化配置，只保留必要的三个参数
        self.default_params = {
            "text": "",
            "text_language": config.get('text_language', "zh"),
            "model_name": config.get('model_name', "default")
        }

    # 在发送消息前，会触发 on_decorating_result 钩子
    @filter.on_decorating_result()
    async def on_llm_response(self, event: AstrMessageEvent):
        """将LLM生成的文本按概率生成语音并发送"""
        if random.random() > self.send_record_probability:  # 概率控制
            return

        chain = event.get_result().chain
        seg = chain[0]

        # 仅允许只含有单条文本的消息链通过
        if not (len(chain) == 1 and seg.type=='Plain'):
            return

        resp_text = seg.text  # ai生成的文本

        # 仅允许一定长度以下的文本通过
        if len(resp_text) > self.max_resp_text_len:
            return

        # 使用简化的参数结构
        params = {
            "text": resp_text,
            "text_language": self.default_params["text_language"],
            "model_name": self.default_params["model_name"]
        }

        file_name = self.generate_file_name(event, params=params) # 生成文件名
        save_path = await self.tts_inference(params=params, file_name=file_name)  # 生成语音

        if save_path is None:
            logger.error("TTS任务执行失败！")
            return

        chain.clear() # 清空消息段
        chain.append(Record.fromFileSystem(save_path)) # 新增语音消息段



    @filter.command("说")
    async def on_regex(self, event: AstrMessageEvent, send_text: str = None):
        """说xxx，直接调用TTS，发送合成后的语音"""
        if not send_text:
            return

        # 使用简化的参数结构
        params = {
            "text": send_text,
            "text_language": self.default_params["text_language"],
            "model_name": self.default_params["model_name"]
        }

        file_name = self.generate_file_name(event, params=params)
        save_path = await self.tts_inference(params=params, file_name=file_name)

        if save_path is None:
            logger.error("TTS任务执行失败！")
            return

        chain = [Record.fromFileSystem(save_path)]
        yield event.chain_result(chain)


    def generate_file_name(self,event: AstrMessageEvent, params) -> str:
        """生成文件名"""
        group_id = event.get_group_id() or '0'
        sender_id = event.get_sender_id() or '0'
        sanitized_text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\s]', '', params["text"])
        limit_text = sanitized_text.strip()[:30]  # 限制长度
        file_name = f"{group_id}_{sender_id}_{limit_text}.wav"  # 固定使用wav格式
        return file_name


    async def tts_inference(self, params, file_name: str = None) -> str | None:
        """发送TTS请求，获取音频内容"""
        endpoint = f"{self.base_url}/"
        # 准备JSON数据
        json_data = {
            "text": params.get("text", ""),
            "text_language": params.get("text_language", "zh"),
            "model_name": params.get("model_name", "default")
        }
        # 使用POST请求发送JSON数据
        response = requests.post(endpoint, json=json_data)
        if response.status_code != 200:
            return None
        audio_bytes: bytes = response.content
        save_path = str(SAVED_AUDIO_DIR / file_name)
        with open(save_path, 'wb') as audio_file:
            audio_file.write(audio_bytes)
        return save_path


    @filter.command("重启TTS", alias={"重启tts"})
    async def tts_control(self,event: AstrMessageEvent):
        """重启TTS服务"""
        yield event.plain_result(f"重启TTS中...(报错信息请忽略，等待一会即可完成重启)")
        endpoint = f"{self.base_url}/control"
        params = {"command": "restart"}
        try:
            response = requests.get(endpoint, params=params)
            if response.status_code == 200:
                logger.info("TTS服务重启成功")
            else:
                logger.error(f"TTS服务重启失败，状态码：{response.status_code}")
        except Exception as e:
            logger.error(f"TTS服务重启出错：{e}")






