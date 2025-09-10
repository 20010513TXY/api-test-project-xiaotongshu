import requests
import pytest
import allure
from config import BASE_URL, SEND_CODE_URL, LOGIN_URL, NOTE_DETAIL_URL


# -------------------------- 1. 新增 Fixture（复用性强，减少重复代码） --------------------------
@pytest.fixture(scope="module", autouse=True)
def module_setup_teardown():
    """
    模块级 Fixture（所有测试类执行前后各1次），自动执行（autouse=True）
    作用：初始化测试环境、清理资源
    """
    with allure.step("【模块初始化】测试开始，初始化全局环境"):
        print("\n===== 接口测试模块开始 =====")
        # 可扩展：比如提前启动测试服务、初始化测试数据库等

    # yield 前是前置操作，后是后置操作
    yield

    with allure.step("【模块清理】测试结束，清理测试环境"):
        print("===== 接口测试模块结束 =====")
        # 可扩展：比如关闭测试服务、删除测试数据等


@pytest.fixture(scope="function")
def req_session():
    """
    函数级 Fixture（每个测试用例执行前1次）
    作用：创建 requests 会话（保持连接复用，比单次请求高效），自动关闭会话
    """
    with allure.step("【请求初始化】创建 requests 会话"):
        session = requests.Session()  # 会话对象：复用TCP连接，提升效率
        yield session  # 把会话对象传给测试用例

    with allure.step("【请求清理】关闭 requests 会话"):
        session.close()  # 自动关闭会话，避免资源泄露


@pytest.fixture(scope="function")
def get_login_token(req_session):
    """
    模块级 Fixture（所有测试类共享）
    作用：提前获取“有效Token”，供需要登录的接口（如笔记详情）直接使用
    """
    with allure.step("【Token获取】通过正确账号登录，获取有效Token"):
        login_payload = {
            "phone": "13350180915",
            "password": "123456",
            "type": 2
        }
        login_url = f"{BASE_URL}{LOGIN_URL}"
        response = req_session.post(url=login_url, json=login_payload)
        login_result = response.json()

        # 确保Token获取成功（否则后续依赖接口会失败）
        assert response.status_code == 200, "获取Token的登录请求失败"
        assert login_result.get("success") is True, "获取Token的登录逻辑失败"
        assert login_result.get("data") is not None, "登录响应中无Token"

        valid_token = login_result.get("data")
        print(f"【获取到有效Token】: {valid_token[:20]}...")  # 打印前20位，避免敏感信息暴露
        return valid_token  # 返回Token，供其他用例调用


# -------------------------- 2. 验证码发送接口（补充参数化，批量测试） --------------------------
# 验证码接口参数化数据：(手机号, 预期success, 预期包含的提示, 场景描述)
send_code_param_data = [
    # 正常场景
    ("13350180921", True, None, "正确11位手机号"),
    # 异常场景
    ("", False, "不能为空", "手机号为空"),
    ("133501809", False, "格式不正确", "10位手机号（格式错误）"),
    ("1335018092123", False, "格式不正确", "13位手机号（格式错误）"),
    ("133abc80921", False, "格式不正确", "手机号含字母（格式错误）"),
    ("133*5018092", False, "格式不正确", "手机号含特殊字符（格式错误）")
]


@allure.feature("1. 验证码发送接口")
class TestSendVerificationCode:
    @allure.story("验证码发送场景（参数化批量测试）")
    @allure.title("验证码测试：{scene_desc}")  # 标题带场景描述，报告更清晰
    # 参数化装饰器：把 send_code_param_data 数据批量传入测试用例
    @pytest.mark.parametrize("phone, expect_success, expect_msg, scene_desc", send_code_param_data)
    def test_send_code_parametrize(self, req_session, phone, expect_success, expect_msg, scene_desc):
        """参数化测试：批量覆盖验证码发送的正常/异常场景"""
        # 1. 接口信息
        send_url = f"{BASE_URL}{SEND_CODE_URL}"
        payload = {"phone": phone}

        # 2. 发送请求（使用 Fixture 的会话对象）
        with allure.step(f"发送POST请求：手机号={phone}"):
            response = req_session.post(url=send_url, json=payload)
            print(f"\n【{scene_desc}】响应内容: {response.text}")

        # 3. 断言（分步骤验证，失败时定位更精准）
        with allure.step("验证HTTP状态码为200"):
            assert response.status_code == 200, f"状态码异常：预期200，实际{response.status_code}"

        response_json = response.json()
        with allure.step(f"验证success标识：预期{expect_success}"):
            assert response_json.get("success") is expect_success, \
                f"success异常：预期{expect_success}，实际{response_json.get('success')}"

        with allure.step(f"验证提示信息：包含「{expect_msg}」"):
            actual_msg = response_json.get("message", "")  # 兼容message字段不存在的情况
            assert expect_msg in actual_msg, \
                f"提示信息异常：预期包含「{expect_msg}」，实际「{actual_msg}」"


# -------------------------- 3. 登录接口（补充参数化+失败用例） --------------------------
# 登录接口参数化数据：(手机号, 密码, 类型, 预期success, 预期提示, 场景描述)
login_param_data = [
    # 正常场景
    ("13350180915", "123456", 2, True, None, "正确账号密码登录"),
    # 失败场景（新增）
    ("13350180915", "1234567", 2, False, "AUTH-20004", "密码错误登录"),
    ("13350180999", "123456", 2, False, "AUTH-20003", "手机号未注册登录"),
    ("13350180915", "", 2, False, "AUTH-20004", "密码为空登录"),
    ("", "123456", 2, False, "AUTH-10001", "手机号为空登录"),
    ("13350180915", "123456", 99, False, "AUTH-10000", "登录类型非法（99不存在）")
]


@allure.feature("2. 用户登录接口")
class TestAuthLogin:
    @allure.story("登录场景（参数化批量测试：正常+失败）")
    @allure.title("登录测试：{scene_desc}")
    @pytest.mark.parametrize("phone, password, login_type, expect_success, expect_errorCode, scene_desc", login_param_data)
    def test_login_parametrize(self, req_session, phone, password, login_type, expect_success, expect_errorCode, scene_desc):
        """参数化测试：覆盖登录的正常场景+5种失败场景"""
        # 1. 接口信息
        login_url = f"{BASE_URL}{LOGIN_URL}"
        login_payload = {
            "phone": phone,
            "password": password,
            "type": login_type
        }

        # 2. 发送请求
        with allure.step(f"发送登录请求：{scene_desc}"):
            response = req_session.post(url=login_url, json=login_payload)
            print(f"\n【{scene_desc}】登录响应: {response.text}")

        # 3. 断言
        with allure.step("验证HTTP状态码为200"):
            assert response.status_code == 200, f"登录请求异常：状态码{response.status_code}"

        login_result = response.json()
        with allure.step(f"验证success标识：预期{expect_success}"):
            assert login_result.get("success") is expect_success, \
                f"登录结果异常：预期{expect_success}，实际{login_result.get('success')}"

        with allure.step(f"验证提示信息：包含「{expect_errorCode}」"):
            actual_errorCode = login_result.get("errorCode", "")
            assert expect_errorCode in actual_errorCode, \
                f"提示信息异常：预期包含「{expect_errorCode}」，实际「{actual_errorCode}」"


# -------------------------- 4. 笔记详情接口（补充失败用例，依赖Token Fixture） --------------------------
# 笔记查询参数化数据：(Token, 笔记ID, 预期success, 预期提示, 场景描述)
note_detail_param_data = [
    # 正常场景（使用Fixture获取的有效Token）
    ("valid_token", 1964771849623568408, True, "成功", "有效Token+正确笔记ID"),
    # 失败场景（新增）
    ("invalid_token", 1964771849623568408, False, "Token无效", "无效Token（伪造值）"),
    ("", 1964771849623568408, False, "Token为空", "Token为空（未登录）"),
    ("valid_token", 123456789, False, "笔记不存在", "有效Token+不存在的笔记ID"),
    ("valid_token", "abc123", False, "ID格式错误", "有效Token+笔记ID为字符串（格式错）")
]


@allure.feature("3. 笔记详情查询接口")
class TestNoteDetail:
    @allure.story("笔记查询场景（参数化批量测试：正常+失败）")
    @allure.title("笔记查询测试：{scene_desc}")
    @pytest.mark.parametrize("token_type, note_id, expect_success, expect_msg, scene_desc", note_detail_param_data)
    def test_note_detail_parametrize(
            self, req_session, get_login_token, token_type, note_id, expect_success, expect_msg, scene_desc
    ):
        """
        参数化测试：覆盖笔记查询的正常场景+4种失败场景
        依赖 get_login_token Fixture：直接使用有效Token，无需重复登录
        """
        # 1. 处理Token（区分“有效/无效/空”场景）
        if token_type == "valid_token":
            token = "Bearer " + get_login_token  # 使用Fixture的有效Token
        elif token_type == "invalid_token":
            token = "Bearer fake_token_123456"  # 伪造无效Token
        else:  # token_type == ""
            token = "Bearer "  # Token为空

        # 2. 接口信息（请求头+参数）
        note_url = f"{BASE_URL}{NOTE_DETAIL_URL}"
        headers = {
            "Authorization": token,  # 携带Token（有效/无效/空）
            "Content-Type": "application/json"
        }
        note_payload = {"id": note_id}

        # 3. 发送请求
        with allure.step(f"发送笔记查询请求：{scene_desc}"):
            response = req_session.post(url=note_url, json=note_payload, headers=headers)
            print(f"\n【{scene_desc}】笔记响应: {response.text}")

        # 4. 断言
        with allure.step("验证HTTP状态码为200"):
            assert response.status_code == 200, f"笔记请求异常：状态码{response.status_code}"

        note_result = response.json()
        with allure.step(f"验证success标识：预期{expect_success}"):
            assert note_result.get("success") is expect_success, \
                f"笔记查询结果异常：预期{expect_success}，实际{note_result.get('success')}"

        with allure.step(f"验证提示信息：包含「{expect_msg}」"):
            actual_msg = note_result.get("message", "")
            assert expect_msg in actual_msg, \
                f"提示信息异常：预期包含「{expect_msg}」，实际「{actual_msg}」"

        # 额外断言：正常场景需验证笔记ID正确性
        if expect_success:
            with allure.step("验证返回笔记ID与请求一致"):
                actual_note_id = note_result.get("data", {}).get("id")
                assert actual_note_id == note_id, \
                    f"笔记ID不匹配：预期{note_id}，实际{actual_note_id}"