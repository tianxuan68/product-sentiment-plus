// 获取 views 目录下所有动态页面（vue / tsx）
const allFiles = import.meta.glob('../views/**/*.{vue,tsx}');

export const dynamicPages = { ...allFiles };
