import { ref, unref } from 'vue';
import { defHttp } from '/@/utils/http/axios';
import { useMessage } from '/@/hooks/web/useMessage';
import { useUserStore } from '/@/store/modules/user';
import { getCaptcha, getThirdLoginConfig } from '/@/api/sys/user';
import { encryptPasswordForTransmit } from '/@/utils/cipher';
import { useI18n } from '/@/hooks/web/useI18n';
import { buildThirdLoginRenderUrl, buildThirdLoginCallbackUrl, THIRD_LOGIN_SOURCE_LABELS } from '/@/utils/thirdLoginUrl';

export function useThirdLogin() {
  const { createMessage, notification } = useMessage();
  const { t } = useI18n();
  const userStore = useUserStore();
  const thirdType = ref('');
  const thirdLoginInfo = ref<any>({});
  const thirdLoginState = ref(false);
  const bindingPhoneModal = ref(false);
  const thirdUserUuid = ref('');
  const thirdConfirmShow = ref(false);
  const thirdPasswordShow = ref(false);
  const thirdLoginPassword = ref('');
  const thirdLoginUser = ref('');
  const thirdCreateUserLoding = ref(false);
  const thirdPhone = ref('');
  const thirdCaptcha = ref('');
  const enabledSources = ref<string[]>([]);
  const configLoaded = ref(false);

  async function loadThirdLoginConfig() {
    try {
      const cfg = await getThirdLoginConfig();
      enabledSources.value = cfg?.enabledSources || [];
    } catch {
      enabledSources.value = [];
    } finally {
      configLoaded.value = true;
    }
  }

  function isThirdLoginEnabled(source: string) {
    return enabledSources.value.includes(source);
  }

  function thirdLoginLabel(source: string) {
    return THIRD_LOGIN_SOURCE_LABELS[source] || source;
  }

  async function onThirdLogin(source: string) {
    if (!configLoaded.value) {
      await loadThirdLoginConfig();
    }
    if (!isThirdLoginEnabled(source)) {
      createMessage.warning(
        `${thirdLoginLabel(source)} 登录未启用。请在后端 jeecg-fastapi/.env 配置 OAuth 参数，并将回调地址设为：${buildThirdLoginCallbackUrl(source)}`,
      );
      return;
    }

    const url = buildThirdLoginRenderUrl(source);
    const openWin = window.open(
      url,
      `login ${source}`,
      'height=500, width=500, top=0, left=0, toolbar=no, menubar=no, scrollbars=no, resizable=no,location=no, status=no',
    );
    thirdType.value = source;
    thirdLoginInfo.value = {};
    thirdLoginState.value = false;

    const receiveMessage = function (event: MessageEvent) {
      const token = event.data;
      if (typeof token === 'string') {
        if (token === '登录失败') {
          createMessage.warning(token);
        } else if (token.includes('绑定手机号')) {
          bindingPhoneModal.value = true;
          const strings = token.split(',');
          thirdUserUuid.value = strings[1];
        } else if (token.includes('未配置') || token.includes('不支持')) {
          createMessage.warning(token);
        } else {
          doThirdLogin(token);
        }
      } else if (typeof token === 'object' && token?.isObj === true) {
        thirdConfirmShow.value = true;
        thirdLoginInfo.value = { ...token };
      } else if (token != null) {
        createMessage.warning('不识别的信息传递');
      }
      if (openWin?.closed) {
        window.removeEventListener('message', receiveMessage, false);
      }
    };
    window.removeEventListener('message', receiveMessage, false);
    window.addEventListener('message', receiveMessage, false);
  }

  function doThirdLogin(token: string) {
    if (unref(thirdLoginState) === false) {
      thirdLoginState.value = true;
      userStore.ThirdLogin({ token, thirdType: unref(thirdType) }).then((res) => {
        if (res && res.userInfo) {
          notification.success({
            message: t('sys.login.loginSuccessTitle'),
            description: `${t('sys.login.loginSuccessDesc')}: ${res.userInfo.realname}`,
            duration: 3,
          });
        } else {
          requestFailed(res);
        }
      });
    }
  }

  function requestFailed(err: any) {
    notification.error({
      message: '登录失败',
      description: ((err.response || {}).data || {}).message || err.message || '请求出现错误，请稍后再试',
      duration: 4,
    });
  }

  function thirdLoginUserBind() {
    thirdLoginPassword.value = '';
    thirdLoginUser.value = thirdLoginInfo.value.uuid;
    thirdConfirmShow.value = false;
    thirdPasswordShow.value = true;
  }

  function thirdLoginUserCreate() {
    thirdCreateUserLoding.value = true;
    thirdLoginInfo.value.suffix = parseInt(String(Math.random() * 98 + 1));
    defHttp
      .post({ url: '/sys/third/user/create', params: { thirdLoginInfo: unref(thirdLoginInfo) } }, { isTransformResponse: false })
      .then((res) => {
        if (res.success) {
          doThirdLogin(res.result);
          thirdConfirmShow.value = false;
        } else {
          createMessage.warning(res.message);
        }
      })
      .finally(() => {
        thirdCreateUserLoding.value = false;
      });
  }

  function thirdLoginCheckPassword() {
    const params = Object.assign({}, unref(thirdLoginInfo), {
      password: encryptPasswordForTransmit(unref(thirdLoginPassword)),
    });
    defHttp.post({ url: '/sys/third/user/checkPassword', params }, { isTransformResponse: false }).then((res) => {
      if (res.success) {
        thirdLoginNoPassword();
        doThirdLogin(res.result);
      } else {
        createMessage.warning(res.message);
      }
    });
  }

  function thirdLoginNoPassword() {
    thirdPasswordShow.value = false;
    thirdLoginPassword.value = '';
    thirdLoginUser.value = '';
  }

  function sendCodeApi() {
    return getCaptcha({ mobile: unref(thirdPhone), smsmode: '0' });
  }

  function thirdHandleOk() {
    if (!unref(thirdPhone)) {
      cmsFailed('请输入手机号');
      return;
    }
    if (!unref(thirdCaptcha)) {
      cmsFailed('请输入验证码');
      return;
    }
    defHttp
      .post(
        {
          url: '/sys/thirdLogin/bindingThirdPhone',
          params: {
            mobile: unref(thirdPhone),
            captcha: unref(thirdCaptcha),
            thirdUserUuid: unref(thirdUserUuid),
          },
        },
        { isTransformResponse: false },
      )
      .then((res) => {
        if (res.success) {
          bindingPhoneModal.value = false;
          doThirdLogin(res.result);
        } else {
          createMessage.warning(res.message);
        }
      });
  }

  function cmsFailed(err: string) {
    notification.error({
      message: '登录失败',
      description: err,
      duration: 4,
    });
  }

  loadThirdLoginConfig();

  return {
    thirdPasswordShow,
    thirdLoginCheckPassword,
    thirdLoginNoPassword,
    thirdLoginPassword,
    thirdConfirmShow,
    thirdCreateUserLoding,
    thirdLoginUserCreate,
    thirdLoginUserBind,
    bindingPhoneModal,
    thirdHandleOk,
    thirdPhone,
    thirdCaptcha,
    onThirdLogin,
    sendCodeApi,
    enabledSources,
    configLoaded,
    isThirdLoginEnabled,
    loadThirdLoginConfig,
  };
}
