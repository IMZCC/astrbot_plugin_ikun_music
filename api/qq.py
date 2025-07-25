import aiohttp
import asyncio
import json
import base64
import urllib.parse
import re
import html
from typing import Dict, List, Optional, Union


class QQMusicAPI:
    BASE_URL = "https://u.y.qq.com"
    UPDATE_URL = "https://api.ikunshare.com:8000/script/qq?key=QQ_21089b3a-NVX96FT6I4G9JCES"

    def __init__(self, **kwargs):
        self.session = aiohttp.ClientSession()
        self.page_size = kwargs.get("page_size", 20)
        self.common_headers = {
            "referer": "https://y.qq.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/106.0.0.0 Safari/537.36",
            "Cookie": "uin=",
        }
        self.search_type_map = {
            0: "song",
            2: "album", 
            1: "singer",
            3: "songlist",
            7: "song",
            12: "mv",
        }
        self.quality_levels = {
            "low": "128k",
            "standard": "320k", 
            "high": "flac",
            "super": "hires",
        }
        self.type_map = {
            "m4a": {"s": "C400", "e": ".m4a"},
            "128": {"s": "M500", "e": ".mp3"},
            "320": {"s": "M800", "e": ".mp3"},
            "ape": {"s": "A000", "e": ".ape"},
            "flac": {"s": "F000", "e": ".flac"},
        }
        self.API_URL = "https://api.ikunshare.top:8000"
        self.API_KEY = kwargs.get("api_key")

    async def close(self):
        await self.session.close()

    def format_music_item(self, item: dict) -> dict:
        """格式化音乐项目"""
        # 适配QQ音乐API的数据结构
        singers = item.get("singer", [])
        if isinstance(singers, list):
            artist = ", ".join([s.get("name", "") for s in singers])
        else:
            artist = ""
            
        # 处理专辑信息
        album_mid = item.get("albummid", "")
        album_name = item.get("albumname", "")
        
        return {
            "id": item.get("songmid") or item.get("id"),
            "songmid": item.get("songmid") or item.get("id"),
            "title": item.get("songname") or item.get("title"),
            "artist": artist,
            "artwork": f"https://y.gtimg.cn/music/photo_new/T002R800x800M000{album_mid}.jpg" if album_mid else None,
            "album": album_name,
            "lrc": item.get("lyric"),
            "albumid": item.get("albumid"),
            "albummid": album_mid,
            "duration": item.get("interval", 0) * 1000  # 转换为毫秒
        }

    def format_album_item(self, item: dict) -> dict:
        """格式化专辑项目"""
        album_mid = item.get("albumMID") or item.get("album_mid") or item.get("albummid")
        
        return {
            "id": item.get("albumID") or item.get("albumid"),
            "albumMID": album_mid,
            "title": item.get("albumName") or item.get("album_name") or item.get("albumname"),
            "artwork": item.get("albumPic") or f"https://y.gtimg.cn/music/photo_new/T002R800x800M000{album_mid}.jpg" if album_mid else None,
            "publishDate": item.get("publicTime") or item.get("pub_time") or item.get("publish_time"),
            "singerID": item.get("singerID") or item.get("singer_id"),
            "artist": item.get("singerName") or item.get("singer_name") or item.get("singername"),
            "singerMID": item.get("singerMID") or item.get("singer_mid"),
            "description": item.get("desc")
        }

    def format_artist_item(self, item: dict) -> dict:
        """格式化歌手项目"""
        return {
            "name": item.get("singerName") or item.get("singer_name") or item.get("singername"),
            "id": item.get("singerID") or item.get("singer_id") or item.get("singerid"),
            "singerMID": item.get("singerMID") or item.get("singer_mid") or item.get("singermid"),
            "avatar": item.get("singerPic") or item.get("singer_pic"),
            "albumCount": item.get("songNum", 0) or item.get("song_num", 0)
        }

    def change_url_query(self, params: dict, base_url: str) -> str:
        """修改URL查询参数"""
        parsed = urllib.parse.urlparse(base_url)
        query_dict = urllib.parse.parse_qs(parsed.query)
        
        for key, value in params.items():
            if value is not None and value != "":
                query_dict[key] = [str(value)]
        
        new_query = urllib.parse.urlencode(query_dict, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_query))

    async def _request(self, url: str, method: str = "GET", data: dict = None, headers: dict = None):
        """统一请求接口"""
        request_headers = self.common_headers.copy()
        if headers:
            request_headers.update(headers)
            
        if method.upper() == "POST":
            async with self.session.post(url, json=data, headers=request_headers) as response:
                text = await response.text()
                # 处理可能的JSONP格式
                text = re.sub(r'callback\(|MusicJsonCallback\(|jsonCallback\(|\)$', '', text)
                try:
                    return json.loads(text)
                except:
                    return {}
        else:
            async with self.session.get(url, headers=request_headers) as response:
                text = await response.text()
                # 处理可能的JSONP格式
                text = re.sub(r'callback\(|MusicJsonCallback\(|jsonCallback\(|\)$', '', text)
                try:
                    return json.loads(text)
                except:
                    return {}

    async def search_base(self, query: str, page: int, search_type: int):
        """基础搜索方法"""
        # 使用QQ音乐移动端搜索API
        params = {
            'ct': 24,
            'qqmusic_ver': 1298,
            'new_json': 1,
            'remoteplace': 'txt.yqq.center',
            'searchid': 60997426,
            't': search_type,
            'aggr': 1,
            'cr': 1,
            'catZhida': 1,
            'lossless': 0,
            'flag_qc': 0,
            'p': page,
            'n': self.page_size,
            'w': query,
            'g_tk': 5381,
            'loginUin': 0,
            'hostUin': 0,
            'format': 'json',
            'inCharset': 'utf8',
            'outCharset': 'utf-8',
            'notice': 0,
            'platform': 'h5',
            'needNewCode': 1
        }
        
        url = "https://c.y.qq.com/soso/fcgi-bin/search_for_qq_cp"
        
        async with self.session.get(url, params=params, headers=self.common_headers) as response:
            text = await response.text()
            # 处理可能的JSONP格式
            text = re.sub(r'callback\(|MusicJsonCallback\(|jsonCallback\(|\)$', '', text)
            try:
                response_data = json.loads(text)
            except:
                return {"isEnd": True, "data": []}
        
        data = response_data.get("data", {})
        
        if search_type == 0:  # 歌曲搜索
            items = data.get("song", {}).get("list", [])
            total = data.get("song", {}).get("totalnum", 0)
        elif search_type == 2:  # 专辑搜索
            items = data.get("album", {}).get("list", [])
            total = data.get("album", {}).get("totalnum", 0)
        elif search_type == 1:  # 歌手搜索
            items = data.get("singer", {}).get("list", [])
            total = data.get("singer", {}).get("totalnum", 0)
        elif search_type == 3:  # 歌单搜索
            items = data.get("songlist", {}).get("list", [])
            total = data.get("songlist", {}).get("totalnum", 0)
        else:
            items = []
            total = 0
        
        return {
            "isEnd": total <= page * self.page_size,
            "data": items
        }

    async def search_music(self, query: str, page: int):
        """搜索音乐"""
        result = await self.search_base(query, page, 0)
        
        return {
            "isEnd": result["isEnd"],
            "data": [self.format_music_item(item) for item in result["data"]]
        }

    async def search_album(self, query: str, page: int):
        """搜索专辑"""
        try:
            result = await self.search_base(query, page, 2)
            return {
                "isEnd": result["isEnd"],
                "data": [self.format_album_item(item) for item in result["data"]]
            }
        except Exception as e:
            # 如果专辑搜索失败，返回空结果
            print(f"专辑搜索出错: {e}")
            return {"isEnd": True, "data": []}

    async def search_artist(self, query: str, page: int):
        """搜索歌手"""
        try:
            result = await self.search_base(query, page, 1)
            return {
                "isEnd": result["isEnd"],
                "data": [self.format_artist_item(item) for item in result["data"]]
            }
        except Exception as e:
            # 如果歌手搜索失败，返回空结果
            print(f"歌手搜索出错: {e}")
            return {"isEnd": True, "data": []}

    async def search_playlist(self, query: str, page: int):
        """搜索歌单"""
        try:
            result = await self.search_base(query, page, 3)
            playlists = []
            
            for item in result["data"]:
                playlists.append({
                    "id": item.get("dissid"),
                    "title": item.get("dissname"),
                    "creator": item.get("creator", {}).get("name"),
                    "playCount": item.get("listennum", 0),
                    "trackCount": item.get("song_count", 0),
                    "artwork": item.get("imgurl"),
                    "description": item.get("introduction")
                })
            
            return {
                "isEnd": result["isEnd"],
                "data": playlists
            }
        except Exception as e:
            # 如果歌单搜索失败，返回空结果
            print(f"歌单搜索出错: {e}")
            return {"isEnd": True, "data": []}

    async def search_lyric(self, query: str, page: int):
        """搜索歌词"""
        try:
            result = await self.search_base(query, page, 7)
            lyrics = []
            
            for item in result["data"]:
                formatted_item = self.format_music_item(item)
                # 保持与网易云音乐API一致的字段名
                formatted_item["rawLyrics"] = item.get("content")
                lyrics.append(formatted_item)
            
            return {
                "isEnd": result["isEnd"],
                "data": lyrics
            }
        except Exception as e:
            # 如果歌词搜索失败，返回空结果
            print(f"歌词搜索出错: {e}")
            return {"isEnd": True, "data": []}

    async def get_media_source(self, song_id: str, quality: str = "high"):
        """获取音乐播放链接"""
        if not song_id:
            raise ValueError("song_id 不正确")

        quality_param = self.quality_levels.get(quality)
        if not quality_param:
            raise ValueError(f"未知音质: {quality}，可选：{list(self.quality_levels.keys())}")

        url = f"{self.API_URL}/url?source=tx&songId={song_id}&quality={quality_param}"
        headers = {
            "X-Request-Key": self.API_KEY,
        }
        
        async with self.session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            result = await resp.json()
            return {"url": result.get("url")}

    async def get_lyric(self, music_item: dict):
        """获取歌词"""
        songmid = music_item.get("songmid")
        if not songmid:
            return {"rawLrc": "", "translation": ""}
            
        import time
        url = (f"http://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
               f"?songmid={songmid}&pcachetime={int(time.time() * 1000)}"
               f"&g_tk=5381&loginUin=0&hostUin=0&inCharset=utf8&outCharset=utf-8"
               f"&notice=0&platform=yqq&needNewCode=0")
        
        headers = {"Referer": "https://y.qq.com", "Cookie": "uin="}
        
        async with self.session.get(url, headers=headers) as response:
            text = await response.text()
            # 移除jsonp回调
            text = re.sub(r'callback\(|MusicJsonCallback\(|jsonCallback\(|\)$', '', text)
            
            try:
                result = json.loads(text)
                raw_lyric = ""
                translation = ""
                
                if result.get("lyric"):
                    raw_lyric = base64.b64decode(result["lyric"]).decode('utf-8')
                    
                if result.get("trans"):
                    translation = base64.b64decode(result["trans"]).decode('utf-8')
                
                return {
                    "rawLrc": raw_lyric,
                    "translation": translation
                }
            except:
                return {"rawLrc": "", "translation": ""}

    async def get_album_info(self, album_item: dict):
        """获取专辑信息"""
        album_mid = album_item.get("albumMID")
        if not album_mid:
            return {"musicList": []}
            
        data = {
            "comm": {"ct": 24, "cv": 10000},
            "albumSonglist": {
                "method": "GetAlbumSongList",
                "param": {
                    "albumMid": album_mid,
                    "albumID": 0,
                    "begin": 0,
                    "num": 999,
                    "order": 2,
                },
                "module": "music.musichallAlbum.AlbumSongList",
            },
        }
        
        url = self.change_url_query(
            {"data": json.dumps(data)},
            "https://u.y.qq.com/cgi-bin/musicu.fcg?g_tk=5381&format=json&inCharset=utf8&outCharset=utf-8"
        )
        
        response = await self._request(url)
        song_list = response.get("albumSonglist", {}).get("data", {}).get("songList", [])
        
        return {
            "musicList": [self.format_music_item(item.get("songInfo", {})) for item in song_list]
        }

    async def import_music_sheet(self, url_like: str):
        """导入歌单"""
        # 提取歌单ID
        sheet_id = None
        
        patterns = [
            r'https?://i\.y\.qq\.com/n2/m/share/details/taoge\.html\?.*id=([0-9]+)',
            r'https?://y\.qq\.com/n/ryqq/playlist/([0-9]+)',
            r'^(\d+)$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_like)
            if match:
                sheet_id = match.group(1)
                break
                
        if not sheet_id:
            return []
            
        url = (f"http://i.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
               f"?type=1&utf8=1&disstid={sheet_id}&loginUin=0")
        
        headers = {"Referer": "https://y.qq.com/n/yqq/playlist", "Cookie": "uin="}
        
        async with self.session.get(url, headers=headers) as response:
            text = await response.text()
            # 移除jsonp回调
            text = re.sub(r'callback\(|MusicJsonCallback\(|jsonCallback\(|\)$', '', text)
            
            try:
                result = json.loads(text)
                song_list = result.get("cdlist", [{}])[0].get("songlist", [])
                return [self.format_music_item(song) for song in song_list]
            except:
                return []

    async def fetch_extra(self, song_id: str):
        """获取额外信息 - 使用songmid"""
        # QQ音乐可能需要不同的API来获取额外信息
        # 这里返回基本格式，可以根据需要扩展
        return {
            "title": "",
            "artist": "",
            "album": "",
            "cover": "",
            "link": "",
        }


# 示例测试方法
async def main():
    api = QQMusicAPI(page_size=20,api_key="")
    try:
        # 搜索音乐
        ret = await api.search_music("恒温", 1)
        print(f"找到以下歌曲喵~\n" + "\n".join(
            f"{i + 1}. {song['title']} - {song['artist']} ({song['duration'] // 1000}秒)"
            for i, song in enumerate(ret['data'])
        ))
        print(ret)
        
        if ret['data']:
            # 获取第一首歌的播放链接
            music_item = ret["data"][0]
            songmid = music_item.get('songmid')
            
            if songmid:
                resp = await api.get_media_source(songmid, "high")
                print(f"歌曲{music_item['title']} 播放链接：{resp}")
                
                # 获取歌词
                lyric = await api.get_lyric(music_item)
                print(f"歌词：{lyric.get('rawLrc', '')[:100]}...")
                
    except Exception as e:
        print(f"测试出错: {e}")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
