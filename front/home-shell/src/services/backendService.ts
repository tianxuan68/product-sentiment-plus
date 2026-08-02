import { request } from '../api/apiClient';

export type User = { username: string; displayName: string; avatar: string };
export type Insight = { id: string; label: string; title: string; body: string; tone: string; icon: 'wave' | 'spark' | 'pulse' };

const mockUser: User = { username: 'dxx', displayName: 'Dxx', avatar: 'D' };
const mockInsights: Insight[] = [
  { id: 'ins-01', label: '情绪趋势', title: '本周品牌好感度正在回升', body: '基于 12,840 条真实反馈，正向情绪较上周提升 8.6%。', tone: 'teal', icon: 'wave' },
  { id: 'ins-02', label: '用户声音', title: '“轻松上手”成为高频关键词', body: '用户在最近的评价中持续提到体验顺滑、反馈及时。', tone: 'blue', icon: 'spark' },
  { id: 'ins-03', label: '行动建议', title: '让热爱转化为下一次选择', body: '还有 3 个可验证的优化机会，等待你打开。', tone: 'peach', icon: 'pulse' },
];

export async function getUserInfo(): Promise<User> {
  if (import.meta.env.VITE_USE_MOCK !== 'false') return Promise.resolve(mockUser);
  return request<User>('/api/user/info');
}
export async function getInsights(): Promise<Insight[]> {
  if (import.meta.env.VITE_USE_MOCK !== 'false') return Promise.resolve(mockInsights);
  return request<Insight[]>('/api/insights');
}
export async function login(username: string, password: string): Promise<User> {
  if (import.meta.env.VITE_USE_MOCK !== 'false') {
    if (username === 'dxx' && password === 'dxx123456@') return Promise.resolve(mockUser);
    throw new Error('账号或密码不正确');
  }
  return request<User>('/api/auth/login', 'POST', { username, password });
}
