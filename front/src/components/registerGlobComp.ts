import type { App } from 'vue';
import { Icon } from './Icon';
import AIcon from '/@/components/jeecg/AIcon.vue';

import { Button, JUploadButton } from './Button';
import { Space } from 'ant-design-vue';
import { createAsyncComponent } from '/@/utils/factory/createAsyncComponent';

// ant-design-vue 组件通过 unplugin-vue-components + AntDesignVueResolver 自动按需导入，无需手动注册
const compList = [Icon, AIcon, JUploadButton];

export function registerGlobComp(app: App) {
  compList.forEach((comp) => {
    app.component(comp.name || comp.displayName, comp);
  });
  // Space.Compact 是子组件，AntDesignVueResolver 无法自动解析，需手动注册
  app.component('ASpaceCompact', Space.Compact);

  app.component(
    'Tinymce',
    createAsyncComponent(() => import('./Tinymce/src/Editor.vue'), {
      loading: true,
    })
  );
  app.use(Button);
}
