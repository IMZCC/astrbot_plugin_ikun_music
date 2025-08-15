import asyncio
from pathlib import Path
import traceback
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Record
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.platform.sources.wechatpadpro.wechatpadpro_message_event import WeChatPadProMessageEvent
import astrbot.api.message_components as Comp
from astrbot.core.utils.session_waiter import (
    session_waiter,
    SessionController,
)


SAVED_SONGS_DIR = Path("data", "plugins_data", "astrbot_plugin_ikun_music", "songs")
SAVED_SONGS_DIR.mkdir(parents=True, exist_ok=True)

@register("ikun_music", "IMZCC", "基于 IKUN 音源的音乐插件", "1.0.0", "https://github.com/IMZCC/astrbot_plugin_ikun_music")
class MyPlugin(Star):
    # 支持的音乐源
    SUPPORTED_SOURCES = {
        "wy": "网易云音乐",
        "qq": "QQ音乐"
    }
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        self.timeout = config.get("timeout", 20)  # 默认超时时间为20秒
        self.send_mode = config.get("send_mode", "text")  # 默认发送模式为卡片
        self.music_source = config.get("music_source", "wy")  # 默认音乐源为wy
        
        # 初始化API
        self.init_api()

    def init_api(self):
        """初始化音乐API"""
        config = self.config
        if self.music_source == 'wy':
            from .api.wy import NetEaseMusicAPI
            self.api = NetEaseMusicAPI(**config)
        elif self.music_source == 'qq':
            from .api.qq import QQMusicAPI
            self.api = QQMusicAPI(**config)


    @filter.command("music")
    async def search_music(self, event: AstrMessageEvent):
        '''搜索用户的点歌或管理音乐源''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        message = event.message_str.replace("music", "").strip()
        args = message.split()
        logger.info(f"Received music command with args: {args}")
        
        # 处理 music source 相关命令
        if args and args[0] == "source":
            if len(args) == 1:
                # 列出支持的音乐源
                source_list = "\n".join([f"{key}: {name}" for key, name in self.SUPPORTED_SOURCES.items()])
                current_source = self.SUPPORTED_SOURCES.get(self.music_source, "未知")
                yield event.plain_result(f"当前音乐源：{self.music_source} ({current_source})\n\n支持的音乐源：\n{source_list}\n\n使用 'music source <源代码>' 切换音乐源")
                return
            elif len(args) == 2:
                # 切换音乐源
                new_source = args[1].lower()
                if new_source not in self.SUPPORTED_SOURCES:
                    yield event.plain_result(f"不支持的音乐源：{new_source}\n支持的音乐源：{', '.join(self.SUPPORTED_SOURCES.keys())}")
                    return
                
                old_source = self.music_source
                self.music_source = new_source
                try:
                    # 重新初始化API
                    self.init_api()
                    source_name = self.SUPPORTED_SOURCES[new_source]
                    yield event.plain_result(f"音乐源已切换为：{new_source} ({source_name})")
                except Exception as e:
                    # 如果初始化失败，回滚到原来的音乐源
                    self.music_source = old_source
                    self.init_api()
                    logger.error(f"切换音乐源失败：{e}")
                    yield event.plain_result(f"切换音乐源失败，已回滚到 {old_source}：{str(e)}")
                return
        
        # 原有的搜索音乐逻辑
        if not args:
            yield event.plain_result("请输入要搜索的歌曲名，或使用 'music source' 查看音乐源设置。")
            return

        # 解析序号和歌名
        index: int = int(args[-1]) if args[-1].isdigit() else 1
        song_name = " ".join(args[:-1]) if args[-1].isdigit() else " ".join(args)

        logger.info(f"点歌请求：{song_name}，序号：{index}")

        # 搜索歌曲
        songs = await self.api.search_music(song_name, index)
        if not songs or 'data' not in songs or not songs['data']:
            yield event.plain_result("没能找到这首歌喵~")
            return
        yield event.plain_result(f"找到以下歌曲喵~\n" + "\n".join(
            f"{i + 1}. {song['title']} - {song['artist']} ({song['duration'] // 1000}秒)"
            for i, song in enumerate(songs['data'])
        ))
        # 延迟一点点
        await asyncio.sleep(0.2)

        @session_waiter(timeout=self.timeout, record_history_chains=False)
        async def empty_mention_waiter(controller: SessionController, event: AstrMessageEvent):
            index = event.message_str
            if not index.isdigit() or int(index) < 1 or int(index) > len(songs['data']):
                await event.send(event.plain_result("请输入正确的序号喵~ 重新来一次吧!"))
                controller.stop()
                return
            selected_song = songs['data'][int(index) - 1]
            # 发送歌曲
            await self._send_song(event=event, song=selected_song)
            

            controller.stop()

        try:
            await empty_mention_waiter(event)  # type: ignore
        except TimeoutError as _:
            yield event.plain_result("点歌超时！")
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("点歌发生错误" + str(e))

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''

    @staticmethod
    def format_time(duration_ms):
        """格式化歌曲时长"""
        duration = duration_ms // 1000

        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
        
    async def _send_song(self, event: AstrMessageEvent, song: dict):
        """发送歌曲"""

        platform_name = event.get_platform_name()
        send_mode = self.send_mode

        # 发卡片
        if platform_name == "aiocqhttp" and send_mode == "card":
            audio_url = (await self.api.get_media_source(song_id=song["id"]))["url"]
            info = await self.api.fetch_extra(str(song["id"]))
            client = event.bot
            is_private  = event.is_private_chat()
            if isinstance(event, AiocqhttpMessageEvent):
                
                payloads: dict = {
                    "message": [
                        {
                            "type": "music",
                            "data": {
                                "type": "163" if self.music_source == "wy" else "qq",
                                "url": info['link'] if self.music_source == "wy" else f'https://y.qq.com/n/ryqq/songDetail/{song["id"]}',
                                'audio': audio_url,
                                "title": song.get("title"),
                                "image": info['cover'] if self.music_source == "wy" else song['artwork'],
                            },
                        }
                    ],
                }
                if is_private:
                    payloads["user_id"] = event.get_sender_id()
                    await client.api.call_action("send_private_msg", **payloads)
                else:
                    payloads["group_id"] = event.get_group_id()
                    await client.api.call_action("send_group_msg", **payloads)
            elif isinstance(event, WeChatPadProMessageEvent):
                payloads: dict = {
                    "AppList": [
                        {
                            "ContentType": 8,
                            "ContentXML": contentXML,
                            "ToUserName": event.get_sender_id() if is_private else event.get_group_id(),
                        }
                    ],
                }
                if is_private:
                    payloads["user_id"] = event.get_sender_id()
                    await client.api.call_action("send_private_msg", **payloads)
                else:
                    payloads["group_id"] = event.get_group_id()
                    await client.api.call_action("send_group_msg", **payloads)
        # 发语音
        elif platform_name in ["telegram", "lark", "aiocqhttp"] and send_mode == "record":
            audio_url = (await self.api.get_media_source(song_id=song["id"]))["url"]
            await event.send(event.chain_result([Record.fromURL(audio_url)]))

        # 发文字
        else:
            audio_url = (await self.api.get_media_source(song_id=song["id"]))["url"]
            song_info_str = (
                f"🎶{song.get('title')} - {song.get('artist')} {self.format_time(song['duration'])}\n"
                f"🔗链接：{audio_url}"
            )
            await event.send(event.plain_result(song_info_str))
