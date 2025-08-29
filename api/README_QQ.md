# QQ音乐API使用说明

## 简介

这是一个移植到Python的QQ音乐API，基于原始JavaScript版本改写，支持音乐搜索、获取播放链接、歌词等功能。

## 功能特性

- ✅ 音乐搜索 - 支持按歌曲名搜索
- ✅ 获取播放链接 - 支持多种音质（low/standard/high/super）
- ⚠️ 专辑搜索 - 部分支持（API限制）
- ⚠️ 歌手搜索 - 部分支持（API限制）
- ⚠️ 歌单搜索 - 部分支持（API限制）

## 快速开始

```python
import asyncio
from qq import QQMusicAPI

async def main():
    # 创建API实例
    api = QQMusicAPI(page_size=20)
    
    try:
        # 搜索音乐
        result = await api.search_music("恒温", 1)
        print(f"找到 {len(result['data'])} 首歌曲")
        
        if result['data']:
            song = result['data'][0]
            print(f"歌曲：{song['title']} - {song['artist']}")
            
            # 获取播放链接
            songmid = song.get('songmid') or song.get('id')
            if songmid:
                media = await api.get_media_source(songmid, "high")
                print(f"播放链接：{media['url']}")
                
    
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## API参考

### 初始化

```python
api = QQMusicAPI(
    page_size=20,  # 每页返回的结果数量，默认20
)
```

### 搜索方法

#### search_music(query, page)
搜索音乐

**参数：**
- `query` (str): 搜索关键词
- `page` (int): 页码，从1开始

**返回：**
```python
{
    "isEnd": bool,  # 是否为最后一页
    "data": [
        {
            "id": str,          # 歌曲ID
            "songmid": str,     # 歌曲MID（用于获取播放链接）
            "title": str,       # 歌曲标题
            "artist": str,      # 歌手名称
            "album": str,       # 专辑名称
            "artwork": str,     # 封面图片URL
            "duration": int,    # 时长（毫秒）
        }
    ]
}
```

#### search_album(query, page)
搜索专辑（功能有限）

#### search_artist(query, page) 
搜索歌手（功能有限）

#### search_playlist(query, page)
搜索歌单（功能有限）


### 播放相关方法

#### get_media_source(song_id, quality)
获取音乐播放链接

**参数：**
- `song_id` (str): 歌曲ID或songmid
- `quality` (str): 音质等级
  - "low": 128k
  - "standard": 320k
  - "high": flac
  - "super": hires

**返回：**
```python
{
    "url": str  # 播放链接
}
```


## 注意事项

1. **API限制**：QQ音乐的搜索API可能会有访问限制，建议合理控制请求频率
2. **音质选择**：高音质需要VIP权限，建议优先使用"standard"音质
3. **错误处理**：所有方法都包含了基本的错误处理，失败时会返回空结果
4. **资源清理**：使用完毕后记得调用`await api.close()`释放连接

## API密钥配置

默认使用内置的API密钥，如果需要自定义：

```python
api = QQMusicAPI()
api.API_KEY = "your_custom_api_key"
```

## 与网易云音乐API的兼容性

本API的接口设计与项目中的网易云音乐API保持一致，可以作为替代音源使用。
