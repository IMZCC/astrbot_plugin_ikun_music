import aiohttp
import asyncio
import base64
import json
import random
import string

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii


class NetEaseCrypto:
    iv = b"0102030405060708"
    nonce = b"0CoJUm6Qyw8W8jud"
    pub_key = "010001"
    modulus = ("00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725"
               "152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312"
               "ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424"
               "d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7")

    @classmethod
    def create_random_key(cls, size=16):
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))

    @classmethod
    def aes_encrypt(cls, text: str, sec_key: str) -> str:
        # AES-128-CBC加密，text utf-8编码，pkcs7填充，sec_key utf-8编码
        text_bytes = text.encode('utf-8')
        sec_key_bytes = sec_key.encode('utf-8')
        cipher = AES.new(sec_key_bytes, AES.MODE_CBC, iv=cls.iv)
        padded_text = pad(text_bytes, AES.block_size)
        encrypted = cipher.encrypt(padded_text)
        return base64.b64encode(encrypted).decode('utf-8')

    @classmethod
    def rsa_encrypt(cls, text: str) -> str:
        # RSA加密（文本反转转16进制），pow(bigint),hex，补0到256长度
        text = text[::-1]
        hex_text = binascii.hexlify(text.encode('utf-8'))
        big_int_text = int(hex_text, 16)
        pub_key = int(cls.pub_key, 16)
        modulus = int(cls.modulus, 16)
        encrypted = pow(big_int_text, pub_key, modulus)
        return format(encrypted, 'x').zfill(256)

    @classmethod
    def encrypt(cls, text: str) -> dict:
        # 两次AES + RSA，生成params和encSecKey
        # 第一次AES用nonce固定key
        # 第二次AES用随机sec_key
        sec_key = cls.create_random_key(16)
        first_enc = cls.aes_encrypt(text, cls.nonce.decode())
        params = cls.aes_encrypt(first_enc, sec_key)
        encSecKey = cls.rsa_encrypt(sec_key)
        return {
            "params": params,
            "encSecKey": encSecKey
        }


class NetEaseMusicAPI:
    BASE_URL = "https://music.163.com"

    def __init__(self, page_size: int = 5, api_key:str = None):
        self.session = aiohttp.ClientSession()
        self.common_headers = {
            "authority": "music.163.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/84.0.4147.135 Safari/537.36",
            "content-type": "application/x-www-form-urlencoded",
            "accept": "application/json",
            "origin": "https://music.163.com",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://music.163.com/search/",
            "accept-language": "zh-CN,zh;q=0.9",
        }
        self.page_size = page_size
        self.API_URL = "https://api.ikunshare.top:8000"
        self.API_KEY = ikun_api_key
        self.timeout = timeout
        self.quality_levels = {
            "low": "128k",
            "standard": "320k",
            "high": "flac",
            "super": "hires",
        }

    async def close(self):
        await self.session.close()

    async def _post(self, url: str, data: dict):
        async with self.session.post(url, headers=self.common_headers, data=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def search_base(self, query: str, page: int, search_type: int):
        data = {
            "s": query,
            "limit": self.page_size,
            "type": search_type,
            "offset": (page - 1) * self.page_size,
            "csrf_token": ""
        }
        text = json.dumps(data)
        encrypted_data = NetEaseCrypto.encrypt(text)
        return await self._post(f"{self.BASE_URL}/weapi/search/get", encrypted_data)

    async def search_music(self, query: str, page: int):
        res = await self.search_base(query, page, 1)
        songs = [
            {
                "id": song["id"],
                "title": song["name"],
                "artist": "、".join([artist["name"] for artist in song["artists"]]),
                "album": song["al"]["name"] if "al" in song else None,
                "duration": song["duration"]
            }
            for song in res.get("result", {}).get("songs", [])
        ]
        total = res.get("result", {}).get("songCount", 0)
        return {
            "isEnd": total <= page * self.page_size,
            "data": songs
        }

    async def search_album(self, query: str, page: int):
        res = await self.search_base(query, page, 10)
        albums = [
            {
                "id": album["id"],
                "title": album["name"],
                "artist": album["artist"]["name"] if "artist" in album else None,
                "artwork": album["picUrl"] if "picUrl" in album else None,
                "publishDate": album.get("publishTime")
            }
            for album in res.get("result", {}).get("albums", [])
        ]
        total = res.get("result", {}).get("albumCount", 0)
        return {
            "isEnd": total <= page * self.page_size,
            "data": albums,
        }

    async def search_artist(self, query: str, page: int):
        res = await self.search_base(query, page, 100)
        artists = [
            {
                "id": artist["id"],
                "name": artist["name"],
                "avatar": artist.get("img1v1Url"),
                "albumCount": artist.get("albumSize", 0)
            }
            for artist in res.get("result", {}).get("artists", [])
        ]
        total = res.get("result", {}).get("artistCount", 0)
        return {
            "isEnd": total <= page * self.page_size,
            "data": artists
        }

    async def search_playlist(self, query: str, page: int):
        res = await self.search_base(query, page, 1000)
        playlists = [
            {
                "id": pl["id"],
                "title": pl["name"],
                "creator": pl["creator"]["nickname"] if "creator" in pl else None,
                "playCount": pl["playCount"],
                "trackCount": pl["trackCount"],
                "artwork": pl.get("coverImgUrl"),
            }
            for pl in res.get("result", {}).get("playlists", [])
        ]
        total = res.get("result", {}).get("playlistCount", 0)
        return {
            "isEnd": total <= page * self.page_size,
            "data": playlists
        }

    async def search_lyric(self, query: str, page: int):
        res = await self.search_base(query, page, 1006)
        songs = res.get("result", {}).get("songs", [])
        lyrics = []
        for s in songs:
            lyrics.append({
                "id": s["id"],
                "title": s["name"],
                "artist": ",".join([ar["name"] for ar in s.get("ar", [])]),
                "album": s.get("al", {}).get("name"),
                "artwork": s.get("al", {}).get("picUrl"),
                "rawLyrics": "\n".join(s.get("lyrics", [])) if s.get("lyrics") else None
            })
        total = res.get("result", {}).get("songCount", 0)
        return {
            "isEnd": total <= page * self.page_size,
            "data": lyrics
        }

    async def get_media_source(self, song_id: str, quality: str = "high"):
        """
        通过第三方API获取网易云音乐歌曲对应质量的播放链接
        :param music_item: 歌曲信息，需包含'id'字段
        :param quality: 音质，low/standard/high/super
        :return: dict, 包含 'url' 键
        """
        if not song_id:
            raise ValueError("song_id 不正确")

        quality_param = self.quality_levels.get(quality)
        if not quality_param:
            raise ValueError(f"未知音质: {quality}，可选：{list(self.quality_levels.keys())}")

        url = f"{self.API_URL}/url?source=wy&songId={song_id}&quality={quality_param}"
        headers = {
            "X-Request-Key": self.API_KEY,
        }
        async with self.session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    

# 示例测试方法：

async def main():
    api = NetEaseMusicAPI()
    ret = await api.search_music("恒温", 1)
    print(f"找到以下歌曲喵~\n" + "\n".join(
            f"{i + 1}. {song['title']} - {song['artist']} ({song['duration'] // 1000}秒)"
            for i, song in enumerate(ret['data'])
        ))

    resp = await api.get_media_source(ret["data"][0]['id'], "high")
    print(f"歌曲{ret['data'][0]['title']}播放链接：{resp['url']}")
    for item in ret["data"]:
        print(item)
    await api.close()

if __name__ == "__main__":
    asyncio.run(main())
