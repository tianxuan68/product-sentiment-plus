import { ref } from 'vue';

/**
 * 精简版占位：原 online 低代码模块已移除
 */
export function useTableColumns(_context: Recordable, _extConfigJson: { value: Recordable }) {
  const columns = ref<Recordable[]>([]);

  return {
    columns,
    downloadRowFile: () => {},
    getImgView: (text: string) => text,
    getPcaText: (text: string) => text,
    getFormatDate: (text: string) => text,
    handleColumnResult: () => {},
    hrefComponent: null,
    viewOnlineCellImage: () => {},
  };
}
