<template>
  <div class="login-form-heading enter-x">
    <h2 v-if="unref(getLoginState) !== LoginStateEnum.LOGIN" class="mb-3 text-2xl font-bold text-center xl:text-3xl xl:text-left">
      {{ getFormTitle }}
    </h2>
    <div v-if="unref(getLoginState) === LoginStateEnum.LOGIN" class="login-form-switches login-form-switches-full">
      <Button size="small" class="is-active" @click="setLoginState(LoginStateEnum.LOGIN)">
        账号登录
      </Button>
      <Button size="small" @click="setLoginState(LoginStateEnum.MOBILE)">
        {{ t('sys.login.mobileSignInFormTitle') }}
      </Button>
      <Button size="small" @click="setLoginState(LoginStateEnum.QR_CODE)">
        {{ t('sys.login.qrSignInFormTitle') }}
      </Button>
    </div>
  </div>
</template>
<script lang="ts" setup>
  import { computed, unref } from 'vue';
  import { Button } from 'ant-design-vue';
  import { useI18n } from '/@/hooks/web/useI18n';
  import { LoginStateEnum, useLoginState } from './useLogin';

  const { t } = useI18n();

  const { getLoginState, setLoginState } = useLoginState();

  const getFormTitle = computed(() => {
    const titleObj = {
      [LoginStateEnum.RESET_PASSWORD]: t('sys.login.forgetFormTitle'),
      [LoginStateEnum.LOGIN]: '账号登录',
      [LoginStateEnum.REGISTER]: t('sys.login.signUpFormTitle'),
      [LoginStateEnum.MOBILE]: t('sys.login.mobileSignInFormTitle'),
      [LoginStateEnum.QR_CODE]: t('sys.login.qrSignInFormTitle'),
    };
    return titleObj[unref(getLoginState)];
  });
</script>
