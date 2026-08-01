<template>
  <div class="aui-content">
    <div class="aui-container">
      <div class="aui-form">
        <div class="aui-image">
          <div class="aui-image-text">
            <h2 class="aui-brand-title">{{ t('sys.login.signInTitle') }}</h2>
            <p class="aui-brand-desc">{{ t('sys.login.signInDesc') }}</p>
          </div>
        </div>
        <div class="aui-formBox aui-formEwm">
          <div class="aui-formWell">
            <form>
              <div class="aui-flex aui-form-nav investment_title" style="padding-bottom: 19px">
                <div class="aui-flex-box activeNav">{{t('sys.login.qrSignInFormTitle')}}</div>
              </div>
              <div class="aui-form-box">
                <div class="aui-account" style="padding: 30px 0">
                  <div class="aui-ewm">
                    <QrCode :value="qrCodeUrl" class="enter-x flex justify-center xl:justify-start" :width="280" />
                  </div>
                </div>
              </div>
              <div class="aui-formButton">
                <a class="aui-linek-code aui-link-register" @click="goBackHandleClick">{{t('sys.login.backSignIn')}}</a>
              </div>
            </form>
          </div>
          <template v-if="enabledThirdSources.length > 0">
            <div class="aui-flex aui-third-text">
              <div class="aui-flex-box aui-third-border">
                <span>{{ t('sys.login.otherSignIn') }}</span>
              </div>
            </div>
            <div class="aui-flex" :class="`${prefixCls}-sign-in-way`">
              <div class="aui-flex-box" v-if="enabledThirdSources.includes('github')">
                <div class="aui-third-login">
                  <a title="github" @click.prevent="onThirdLogin('github')"><GithubFilled /></a>
                </div>
              </div>
              <div class="aui-flex-box" v-if="enabledThirdSources.includes('wechat_enterprise')">
                <div class="aui-third-login">
                  <a title="企业微信" @click.prevent="onThirdLogin('wechat_enterprise')"><icon-font class="item-icon" type="icon-qiyeweixin3" /></a>
                </div>
              </div>
              <div class="aui-flex-box" v-if="enabledThirdSources.includes('dingtalk')">
                <div class="aui-third-login">
                  <a title="钉钉" @click.prevent="onThirdLogin('dingtalk')"><DingtalkCircleFilled /></a>
                </div>
              </div>
              <div class="aui-flex-box" v-if="enabledThirdSources.includes('wechat_open')">
                <div class="aui-third-login">
                  <a title="微信" @click.prevent="onThirdLogin('wechat_open')"><WechatFilled /></a>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
  <!-- 第三方登录相关弹框 -->
  <ThirdModal ref="thirdModalRef"></ThirdModal>
</template>

<script lang="ts" setup name="mini-code-login">
  import { ref, onUnmounted } from 'vue';
  import { getLoginQrcode, getQrcodeToken, getThirdLoginConfig } from '/@/api/sys/user';
  import { useUserStore } from '/@/store/modules/user';
  import { QrCode } from '/@/components/Qrcode/index';
  import ThirdModal from '/@/views/sys/login/ThirdModal.vue';
  import logoImg from '/@/assets/loginmini/icon/jeecg_logo.png';
  import { useI18n } from '/@/hooks/web/useI18n';
  import { useDesign } from "/@/hooks/web/useDesign";
  import { GithubFilled, WechatFilled, DingtalkCircleFilled } from '@ant-design/icons-vue';
  import { IconFont } from '/@/utils/iconfont2';

  const { prefixCls } = useDesign('minilogin');
  const { t } = useI18n();
  const qrCodeUrl = ref<string>('');
  let timer: IntervalHandle;
  const state = ref('0');
  const thirdModalRef = ref();
  const enabledThirdSources = ref<string[]>([]);
  const userStore = useUserStore();
  const emit = defineEmits(['go-back', 'success', 'register']);

  //加载二维码信息
  function loadQrCode() {
    state.value = '0';
    getLoginQrcode().then((res) => {
      qrCodeUrl.value = res.qrcodeId;
      if (res.qrcodeId) {
        openTimer(res.qrcodeId);
      }
    });
  }
  //监控扫码状态
  function watchQrcodeToken(qrcodeId) {
    getQrcodeToken({ qrcodeId: qrcodeId }).then((res) => {
      let token = res.token;
      if (token == '-2') {
        //二维码过期重新获取
        loadQrCode();
        clearInterval(timer);
      }
      //扫码成功
      if (res.success) {
        state.value = '2';
        clearInterval(timer);
        setTimeout(() => {
          userStore.qrCodeLogin(token);
        }, 500);
      }
    });
  }

  /** 开启定时器 */
  function openTimer(qrcodeId) {
    watchQrcodeToken(qrcodeId);
    closeTimer();
    timer = setInterval(() => {
      watchQrcodeToken(qrcodeId);
    }, 1500);
  }

  /** 关闭定时器 */
  function closeTimer() {
    if (timer) clearInterval(timer);
  }

  /**
   * 第三方登录
   * @param type
   */
  function onThirdLogin(type) {
    thirdModalRef.value.onThirdLogin(type);
  }

  /**
   * 初始化表单
   */
  function initFrom() {
    loadQrCode();
    getThirdLoginConfig()
      .then((cfg) => {
        enabledThirdSources.value = cfg?.enabledSources || [];
      })
      .catch(() => {
        enabledThirdSources.value = [];
      });
  }

  /**
   * 返回
   */
  function goBackHandleClick() {
    emit('go-back');
    closeTimer();
  }

  onUnmounted(() => {
    closeTimer();
  });

  defineExpose({
    initFrom,
  });
</script>
<style lang="less" scoped>
@import '/@/assets/loginmini/style/home.less';
@import '/@/assets/loginmini/style/base.less';
</style>
