"""
# RainClassroom-Video-Watcher: 雨课堂视频自动观看脚本

详见 <https://github.com/Accurio/RainClassroom-Video-Watcher>
"""

import sys
import string
import time
import asyncio
import logging
import random
from typing import Any, Literal, Optional, Sequence

####################################################################################################
# 用户和课程信息

authority = "changjiang.yuketang.cn"
session_id = "0123456789abcdefghijklmnopqrstuv"
csrf_token = "0123456789abcdefghijklmnopqrstuv"
xtbz = "ykt"
classroom_id = 12345678

####################################################################################################
# 调试参数（一般无需调整）

logging_level = logging.INFO  # 日志
timedelta = 60*30  # 视频观看日志时间戳提前秒数

####################################################################################################

try:
    import httpx
except ModuleNotFoundError as e:
    print("你需要执行 'pip install httpx[http2]' 以安装 HTTPX")
    exit()

####################################################################################################

class RainClassroomClient:
    """雨课堂客户端接口"""
    def __init__(self, authority: str, session_id: str, csrf_token: str, xtbz: str,
        logging_level = logging.INFO,
    ) -> None:
        # 日志 Logging
        self._logger = logging.getLogger(f"RainClassroomClient {id(self)}")
        if not self._logger.hasHandlers():
            logging_handler = logging.StreamHandler(sys.stdout)
            logging_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s", '%Y-%m-%d %H:%M:%S'))
            self._logger.addHandler(logging_handler)
            self._logger.setLevel(logging_level)

        self._authority = authority
        # 浏览器 Headers
        headers = dict()
        headers['User-Agent'] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0")
        headers['Sec-Fetch-Site'] = 'same-origin'
        headers['Sec-Fetch-Mode'] = 'cors'
        headers['Sec-Fetch-Dest'] = 'empty'
        # 雨课堂 Headers
        headers['X-Csrftoken'] = csrf_token
        headers["xtbz"] = xtbz
        # 雨课堂 Cookies
        cookies = dict()
        cookies['sessionid'] = session_id
        cookies['csrftoken'] = csrf_token
        # cookies["xtbz"] = xtbz
        self._session = httpx.AsyncClient(headers=headers, cookies=cookies,
            limits=httpx.Limits(max_connections=2, keepalive_expiry=60))

        self._logger.info(f"{self._authority=}, {session_id=}, {csrf_token=}, {xtbz=}")

    async def sleep(self, delay: float | int) -> None:
        self._logger.info(f"等待{delay}秒")
        await asyncio.sleep(delay)

    ################################################################################################
    # 请求

    async def _request(self, method: Literal['GET', 'POST'], path: str,
        *, keys: Any | tuple[Any, ...] = (), s: str = '', **kwargs,
    ) -> dict | list[dict]:
        """异步请求"""
        if path.startswith("/api/v3/"):
            code = 'code'
            message = 'msg'
            success = code, 0
        elif path.startswith("/v2/api/"):
            code = 'errcode'
            message = 'errmsg'
            success = code, 0
        else:
            code = 'error_code'
            message = 'msg'
            success = 'success', True
        response = await self._session.request(method, "https://"+self._authority+path, **kwargs)
        data: dict = response.json()
        if not response.is_success or not data.get(success[0]) == success[-1]:
            msg = (f"{s}发生错误，HTTP响应状态为 {response.status_code} {response.reason_phrase}，"
                f"业务响应状态为 {data.get(code)} {data.get(message)}")
            self._logger.critical(msg); raise RuntimeError(msg)
        for key in keys if isinstance(keys, (tuple, list)) else (keys,):
            data = data[key]
        self._logger.debug(f"{s}成功，{len(data)}" if isinstance(data, list) else f"{s}成功")
        return data

    async def _get(self, path: str, *,
        keys: Any | tuple[Any, ...] = (), s: str = '', **kwargs,
    ) -> dict | list[dict]:
        """异步GET请求"""
        return await self._request('GET', path, keys=keys, s=s, **kwargs)

    async def _post(self, path: str, *,
        keys: Any | tuple[Any, ...] = (), s: str = '', **kwargs,
    ) -> dict | list[dict]:
        """异步POST请求"""
        return await self._request('POST', path, keys=keys, s=s, **kwargs)

    ################################################################################################
    # 雨课堂接口

    async def query_user_v2(self) -> dict:
        """查询用户"""
        return await self._get("/v2/api/web/userinfo", keys=('data', 0), s="查询用户")

    async def query_user_v3(self) -> dict:
        """查询用户"""
        return await self._get("/api/v3/user/basic-info", keys='data', s="查询用户")

    async def query_courses(self) -> list[dict]:
        """查询课程"""
        return await self._get("/v2/api/web/courses/list", params=dict(identity=2),
            keys=('data', 'list'), s="查询课程")

    async def query_classroom(self, classroom_id: int) -> dict:
        """查询教室"""
        return await self._get(f"/v2/api/web/classrooms/{classroom_id}", params=dict(role=5),
            keys='data', s=f"查询教室{classroom_id}")

    async def query_logs(self, classroom_id: int,
        actype: int = -1, page: int = 0, offset: int = 100, sort: int = 0,
    ) -> list[dict]:
        """查询学习日志"""
        return await self._get(f"/v2/api/web/logs/learn/{classroom_id}",
            params=dict(actype=actype, page=page, offset=offset, sort=sort),
            keys=('data', "activities"), s=f"查询{classroom_id}学习日志")
  
    async def query_chapters(self,
        classroom_id: int, course_sign: str, university_id: int,
    ) -> list[dict]:
        """查询章节和节点"""
        return await self._get("/mooc-api/v1/lms/learn/course/chapter",
            params=dict(cid=classroom_id, classroom_id=classroom_id,
                sign=course_sign, uv_id=university_id),
            keys=('data', "course_chapter"), s=f"查询{classroom_id}章节和节点")

    async def query_leaf(self, classroom_id: int, leaf_id: int) -> dict:
        """查询章节节点"""
        return await self._get(f"/mooc-api/v1/lms/learn/leaf_info/{classroom_id}/{leaf_id}/",
            headers={"Classroom-Id": str(classroom_id)}, keys='data',
            s=f"查询{classroom_id}章节节点")

    async def query_video_watch_progress(self,
        user_id: int, course_id: int, classroom_id: int, video_id: int, snapshot: int = 1,
    ) -> dict | None:
        """查询视频观看进度"""
        response = await self._session.get(
            f"https://{self._authority}/video-log/get_video_watch_progress/",
            params=dict(user_id=user_id, cid=course_id, classroom_id=classroom_id,
                video_id=video_id, video_type="video", vtype="rate", snapshot=snapshot))
        data: dict[str, dict] = response.json()
        if not response.is_success or not data.get('code') == 0:
            msg = (f"查询视频{video_id}观看进度发生错误，"
                f"HTTP响应状态为 {response.status_code} {response.reason_phrase}，"
                f"业务响应状态为 {data.get('code')} {data.get('message')}")
            self._logger.critical(msg); raise RuntimeError(msg)
        data = data['data'].get(str(video_id))
        msg = f"""进度为{data["rate"]:.2%}""" if data else "进度不存在"
        self._logger.debug(f"查询视频{video_id}观看进度成功，"+msg)
        return data

    async def send_video_logs(self, logs: list[dict]) -> dict:
        """发送视频观看日志"""
        response = await self._session.post(f"https://{self._authority}/video-log/heartbeat/",
            json={"heart_data": logs})
        data: dict = response.json()
        if not response.is_success:
            msg = ("发送视频观看日志发生错误，"
                f"HTTP响应状态为 {response.status_code} {response.reason_phrase}，业务响应为 {data}")
            self._logger.critical(msg); raise RuntimeError(msg)
        self._logger.debug("发送视频观看日志成功")
        return data


####################################################################################################

class AttributeDict(dict):
    """属性字典"""
    __slots__ = ()
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    def copy(self):
        return AttributeDict(self)

class RainClassroomVideoLog(object):
    """雨课堂视频观看日志"""

    _g_mapping = {index: char for index, char in enumerate(string.digits + string.ascii_lowercase)}
    @classmethod
    def _generate_g(cls) -> str:
        """生成参数g"""
        n = random.randint(2**20, 2**20*2)
        s = ''
        while n > 0:
            s = cls._g_mapping[n%36] + s
            n //= 36
        return s

    def __init__(self, *, user_id: int, course_id: int, classroom_id: int, video_id: int,
        sku_id: int, cc_id: int, duration: float | int, timestamp: Optional[int] = None,
        lob: Literal["plat2", "plat", "xt", "ykt", "cloud", "zyk", "mtc"] = "ykt",
        cdn_authority: str = "ali-cdn.xuetangx.com",
    ) -> None:
        self.log = AttributeDict()
        self.log.i = 5
        self.log.et = None
        self.log.p = "web"
        self.log.n = cdn_authority
        self.log.lob = lob
        self.log.cp = 0
        self.log.fp = 0
        self.log.tp = 0
        self.log.sp = 1
        self.log.ts = timestamp or int(time.time_ns()/1000000)
        self.log.u = user_id
        self.log.uip = ''
        self.log.c = course_id
        self.log.v = video_id
        self.log.skuid = sku_id
        self.log.classroomid = classroom_id
        self.log.cc = cc_id
        self.log.d = duration if duration is not None else 0
        self.log.pg = str(video_id) + '_' + self._generate_g()
        self.log.sq = 0
        self.log.t = 'video'
        self.log.cards_id = 0
        self.log.slide = 0
        self.log.v_url = ''

    ################################################################################################
    # 事件

    def on_loadstart(self) -> dict:
        self.log.et = 'loadstart'
        self.log.sq += 1
        log = self.log.copy()
        log.d = 0
        return log

    def on_loadedmetadata(self, msdelay: int = None) -> dict:
        self.log.et = "seeking"
        self.log.ts += msdelay or random.randint(500, 1000)
        self.log.sq += 1
        return self.log.copy()

    def on_loadeddata(self, msdelay: int = None) -> dict:
        self.log.et = 'loadeddata'
        self.log.ts += msdelay or random.randint(50, 100)
        self.log.sq += 1
        return self.log.copy()

    def on_play(self, msdelay: int = None) -> dict:
        self.log.et = 'play'
        self.log.ts += msdelay or random.randint(3000, 10000)
        self.log.sq += 1
        return self.log.copy()

    def on_playing(self, msdelay: int = None) -> dict:
        self.log.et = 'playing'
        self.log.ts += msdelay or random.randint(50, 100)
        self.log.sq += 1
        return self.log.copy()

    def on_heartbeat(self, msoffest: int) -> dict:
        self.log.et = "heartbeat"
        self.log.sq += 1
        self.log.cp += round(msoffest/1000, 1)
        self.log.ts += msoffest
        return self.log.copy()

    def on_pause(self, msdelay: int = None) -> dict:
        self.log.et = 'pause'
        self.log.ts += msdelay or random.randint(0, 50)
        self.log.sq += 1
        return self.log.copy()

    def on_ended(self) -> dict:
        self.log.et = "videoend"
        self.log.ts += random.randint(10, 50)
        self.log.sq += 1
        return self.log.copy()

    ################################################################################################

    @classmethod
    def build_video_logs(cls, *, user_id: int, course_id: int, classroom_id: int, video_id: int,
        sku_id: int, cc_id: int, duration: float | int, timestamp: Optional[int] = None,
        lob: Literal["plat2", "plat", "xt", "ykt", "cloud", "zyk", "mtc"] = "ykt",
        cdn_authority: str = "ali-cdn.xuetangx.com",
    ) -> list[dict]:
        """生成视频日志"""
        logger = cls(user_id=user_id, course_id=course_id, classroom_id=classroom_id,
            video_id=video_id, sku_id=sku_id, cc_id=cc_id, duration=duration, timestamp=timestamp,
            lob=lob, cdn_authority=cdn_authority)
        if duration == 0:
            return [logger.on_loadstart()]
        return [logger.on_loadstart(), logger.on_loadedmetadata(), logger.on_loadeddata(),
            logger.on_play(), logger.on_playing(),
            *(logger.on_heartbeat(5000+random.randint(-50, 50))
                for _ in range(5, int(logger.log.d+1), 5)),
            logger.on_heartbeat(int(logger.log.d%5*1000)), logger.on_pause(), logger.on_ended()]


####################################################################################################

class RainClassroomVideoWatcher(RainClassroomClient):
    """雨课堂视频观看器"""
    def __init__(self,  authority: str, session_id: str, csrf_token: str, xtbz: str,
        classroom_id: int, logging_level = logging.INFO, timedelta: int = 0,
    ) -> None:
        super().__init__(authority, session_id, csrf_token, xtbz, logging_level)
        self.classroom_id = classroom_id
        self.timedelta = timedelta

    ################################################################################################

    def _set_university_id(self, university_id: Optional[int] = None) -> None:
        self.university_id = university_id or self.university_id
        self._session.headers['University-Id'] = str(self.university_id)
        self._session.cookies["university_id"] = str(self.university_id)
        self._session.cookies["uv_id"] = str(self.university_id)

    async def obtain_info(self) -> None:
        """获取用户和课程信息"""
        user = await self.query_user_v3()
        self.user_id = user["id"]
        classroom = await self.query_classroom(self.classroom_id)
        self.course_id = classroom["course_id"]
        self.course_sign = classroom["course_sign"]
        self._set_university_id(classroom["uv_id"])
        self._logger.info(f"获取信息完成，user_id={self.user_id}, course_id{self.course_id}, "
            f"course_sign={self.course_sign}, university_id={self.university_id}")

    ################################################################################################

    @classmethod
    def _get_chapter_leaf(cls, leafs: list[dict], tree: list[dict], leaf_type: int = None) -> None:
        """递归获得章节节点列表"""
        for leaf in tree:
            if leaf_type is None or leaf.get("leaf_type") == leaf_type:
                leafs.append(leaf)
            elif "section_leaf_list" in leaf:
                cls._get_chapter_leaf(leafs, leaf["section_leaf_list"], leaf_type)
            elif "leaf_list" in leaf:
                cls._get_chapter_leaf(leafs, leaf["leaf_list"], leaf_type)

    ################################################################################################

    async def batch_query_leaf(self, chapters_leafs: list[dict]) -> list[dict]:
        """批量查询章节节点"""
        return await asyncio.gather(*tuple(
            self.query_leaf(self.classroom_id, leaf['id'])
            for leaf in chapters_leafs))

    async def batch_query_video_watch_progress(self, leafs: list[dict]) -> list[dict | None]:
        """批量查询视频观看进度"""
        return await asyncio.gather(*tuple(
            self.query_video_watch_progress(
                self.user_id, self.course_id, self.classroom_id, leaf['id'])
            for leaf in leafs))

    async def batch_send_video_logs(self,
        leafs: Sequence[dict], progresses: Optional[Sequence[dict]] = None, default: dict = dict(),
    ) -> list[dict]:
        """批量发送视频观看日志"""
        if progresses is None:
            progresses = [default] * len(leafs)
        return await asyncio.gather(*tuple(
            self.send_video_logs(RainClassroomVideoLog.build_video_logs(
                user_id=self.user_id, course_id=self.course_id,
                classroom_id=self.classroom_id,
                video_id=leaf['id'], sku_id=leaf["sku_id"],
                cc_id=leaf["content_info"]["media"]["ccid"],
                duration=(progress or default).get("video_length", 0),
                timestamp=int(time.time_ns()/1000000)-self.timedelta*1000))
            for leaf, progress in zip(leafs, progresses)))

    ################################################################################################

    async def watch(self):
        """观看视频"""
        await self.obtain_info()

        self._logger.info("获取章节和节点开始")
        chapters_leafs = await self.query_chapters(
            self.classroom_id, self.course_sign, self.university_id)
        videos = list()
        self._get_chapter_leaf(videos, chapters_leafs, leaf_type=0)
        self._logger.info(f"获取章节和节点完成，共{len(chapters_leafs)}节点，共{len(videos)}视频")

        retry = 0
        while retry <= 3:

            # 未完成观看的视频需要视频信息
            if retry == 1:
                self._logger.info("获取章节节点开始")
                videos = await self.batch_query_leaf(videos)
                self._logger.info(f"获取章节节点完成，共{len(videos)}视频")
                await self.sleep(2+len(videos))

            # 第1次仅查询视频观看进度
            if retry >= 1:
                self._logger.info(f"发送视频观看日志开始，共{len(videos)}视频")
                await self.batch_send_video_logs(videos, progresses)
                self._logger.info("发送视频观看日志完成")
                await self.sleep(2+len(videos))

            retry += 1
            self._logger.info(f"第{retry}次获取视频观看进度开始")
            progresses = await self.batch_query_video_watch_progress(videos)
            # 仅获得未完成视频
            videos_progresses = tuple((leaf, progress)
                for leaf, progress in zip(videos, progresses)
                if progress is None or not bool(progress["completed"]))
                # if progress is None or progress["rate"] < 1)

            # 全部为已完成视频
            if not videos_progresses:
                self._logger.info("获取视频观看进度完成，全部视频已完成")
                break
            # 有未完成视频
            else:
                videos, progresses = zip(*videos_progresses)
                self._logger.info(f"获取视频观看进度完成，共{len(videos)}视频未完成")

        # 超过重试次数仍有未完成视频
        else:
            self._logger.error(f"已{retry}次获取视频观看进度，但{len(videos)}视频未完成")


####################################################################################################
# 主函数

if __name__ == '__main__':
    watcher = RainClassroomVideoWatcher(authority=authority,
        session_id=session_id, csrf_token=csrf_token, xtbz=xtbz,
        classroom_id=classroom_id, logging_level=logging_level, timedelta=timedelta)
    asyncio.run(watcher.watch())
