<template>
  <div :class="prefixCls">
    <Badge :count="0" :overflowCount="9" :offset="[-4, 18]" :numberStyle="numberStyle">
      <BellOutlined />
    </Badge>
    <ChangePasswordModal @register="changePwdModal" />
  </div>
</template>
<script lang="ts">
  import { defineComponent, onMounted } from 'vue';
  import { Badge } from 'ant-design-vue';
  import { BellOutlined } from '@ant-design/icons-vue';
  import { useModal } from '/@/components/Modal';
  import { useDesign } from '/@/hooks/web/useDesign';
  import { getToken } from '/@/utils/auth';
  import { defHttp } from '@/utils/http/axios';
  import ChangePasswordModal from './ChangePasswordModal.vue';

  export default defineComponent({
    components: {
      BellOutlined,
      Badge,
      ChangePasswordModal,
    },
    setup() {
      const { prefixCls } = useDesign('header-notify');
      const [changePwdModal, { openModal: openPwdModal }] = useModal();

      onMounted(() => {
        if (getToken()) {
          verifyIzDefaultPwd();
        }
      });

      function verifyIzDefaultPwd() {
        defHttp.get({ url: '/sys/user/verifyIzDefaultPwd' }, { isTransformResponse: false }).then((res) => {
          if (res.success && typeof res.message === 'string' && res.message.indexOf('yes') != -1) {
            openPwdModal(true, {
              oldPassword: res.message.split('_')[1],
            });
          }
        });
      }

      return {
        prefixCls,
        numberStyle: {},
        changePwdModal,
      };
    },
  });
</script>
<style lang="less">
  @prefix-cls: ~'@{namespace}-header-notify';

  .@{prefix-cls} {
    .ant-badge {
      font-size: 18px;

      svg {
        width: 0.9em;
      }
    }
  }
</style>
