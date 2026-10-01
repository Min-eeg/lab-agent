<template>
  <div>
    <!-- 问候区: 按时段问候 + 动态引导(真实数据, 回答"现在该做什么") -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <div class="greet-row">
        <div>
          <div class="greet-title">{{ greeting }}，{{ userInfo?.name || '同学' }}</div>
          <div class="greet-sub">{{ todayText }} · {{ roleLabel }}</div>
          <div class="greet-lead">{{ leadText }}</div>
        </div>
        <span class="sys-name">智能实验室预约系统</span>
      </div>
    </el-card>

    <!-- 主行动区: 一主一次, 主卡随角色变化 -->
    <div class="cta-grid">
      <div class="cta-main" @click="$router.push(mainCta.path)">
        <div>
          <div class="cta-title">{{ mainCta.title }}</div>
          <div class="cta-desc">{{ mainCta.desc }}</div>
        </div>
        <div class="cta-go cta-go-light">{{ mainCta.action }} →</div>
      </div>
      <div class="cta-sub" @click="$router.push('/manager/ai-chat')">
        <div>
          <div class="cta-title">AI 助手</div>
          <div class="cta-desc">说一句"帮我约明天下午"，剩下的交给我</div>
        </div>
        <div class="cta-go">开始对话 →</div>
      </div>
    </div>

    <!-- 快捷入口: 图标卡片, 与左侧菜单同构 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span style="font-weight: 600">快捷入口</span>
      </template>
      <div class="shortcut-grid">
        <div
          v-for="item in shortcuts"
          :key="item.path"
          class="shortcut-card"
          @click="$router.push(item.path)"
        >
          <div class="shortcut-icon">
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
          </div>
          <div class="shortcut-label">{{ item.label }}</div>
        </div>
      </div>
    </el-card>

    <!-- 底部轻数据: 一行, 不喧宾夺主 -->
    <div class="foot-row">
      <span>{{ footText }}</span>
      <span class="foot-link" @click="$router.push(footLink)">查看全部预约 →</span>
    </div>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, ref } from 'vue'
import { useUser } from '@/utils/user'
import { getLabPageList } from '@/api/lab'
import { getReservationPageList } from '@/api/reservation'
import {
  Menu as IconMenu,
  ChatDotRound,
  OfficeBuilding,
  House,
  Setting,
  Tickets,
  DocumentChecked,
  User
} from '@element-plus/icons-vue'

const { userInfo } = useUser()

// ---- 数据(全部来自现有列表接口, page_size=1 只取 total, 开销极小) ----
const labTotal = ref('-') // 开放中的实验室数
const reservationTotal = ref('-') // 预约总量(admin) / 我的预约数(学生)
const pendingTotal = ref(0) // 待审核数(admin=全系统, 学生=本人的, 后端自动按角色过滤)
const approvedTotal = ref(0) // 已通过数(学生引导语用)

const isAdmin = computed(() => userInfo.value?.role === 'admin')
const roleLabel = computed(() => (isAdmin.value ? '管理员' : '学生'))

// ---- 问候与日期 ----
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 9) return '早上好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayText = computed(() => {
  const now = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][now.getDay()]
  return `${now.getMonth() + 1} 月 ${now.getDate()} 日 星期${week}`
})

// ---- 动态引导语: 替代"系统能做什么", 一行话回答"现在该做什么" ----
const leadText = computed(() => {
  if (isAdmin.value) {
    return pendingTotal.value > 0
      ? `今天有 ${pendingTotal.value} 个预约正在等待审核`
      : '暂无待审核的预约，一切井井有条'
  }
  if (reservationTotal.value === '-') return '欢迎回来，看看今天能约哪间实验室？'
  if (reservationTotal.value === 0) return '还没有预约，去逛逛开放中的实验室？'
  return `已通过 ${approvedTotal.value} 条 · 待审核 ${pendingTotal.value} 条`
})

// ---- 主行动卡 ----
const mainCta = computed(() => {
  if (isAdmin.value) {
    return {
      title: '预约审核',
      desc:
        pendingTotal.value > 0
          ? `${pendingTotal.value} 条待处理，早审早安心`
          : '队列已清空，保持下去',
      action: '立即处理',
      path: '/manager/audit-reservation'
    }
  }
  return {
    title: '去预约实验室',
    desc: '选好时段提交，管理员通过就能用',
    action: '去预约',
    path: '/manager/lablist'
  }
})

// ---- 快捷入口: 按角色整体生成, 与左侧菜单一致 ----
const shortcuts = computed(() => {
  if (isAdmin.value) {
    return [
      { label: '实验室管理', path: '/manager/lab', icon: markRaw(House) },
      { label: '设备列表管理', path: '/manager/equipment', icon: markRaw(Setting) },
      { label: '预约审核', path: '/manager/audit-reservation', icon: markRaw(DocumentChecked) },
      { label: '用户管理', path: '/manager/user', icon: markRaw(User) }
    ]
  }
  return [
    { label: '实验室列表', path: '/manager/lablist', icon: markRaw(OfficeBuilding) },
    { label: '我的预约', path: '/manager/my-reservation', icon: markRaw(Tickets) }
  ]
})

// ---- 底部轻数据 ----
const footText = computed(() => {
  if (isAdmin.value) {
    return `开放中的实验室 ${labTotal.value} 间 · 预约总量 ${reservationTotal.value} 条`
  }
  return `开放中的实验室 ${labTotal.value} 间 · 我的预约 ${reservationTotal.value} 条`
})
const footLink = computed(() =>
  isAdmin.value ? '/manager/audit-reservation' : '/manager/my-reservation'
)

onMounted(async () => {
  const safe = async (fn, setter) => {
    try {
      const res = await fn()
      if (res.code === 200) setter(res.data?.total ?? 0)
    } catch {
      /* 首页数据加载失败不阻塞页面 */
    }
  }
  await Promise.all([
    safe(
      () => getLabPageList({ page: 1, page_size: 1, status: 1 }),
      (v) => (labTotal.value = v)
    ),
    safe(
      () => getReservationPageList({ page: 1, page_size: 1 }),
      (v) => (reservationTotal.value = v)
    ),
    safe(
      () => getReservationPageList({ page: 1, page_size: 1, status: 0 }),
      (v) => (pendingTotal.value = v)
    ),
    safe(
      () => getReservationPageList({ page: 1, page_size: 1, status: 1 }),
      (v) => (approvedTotal.value = v)
    )
  ])
})
</script>

<style scoped>
/* ---- 问候区 ---- */
.greet-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.greet-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}
.greet-sub {
  margin-top: 6px;
  color: #909399;
  font-size: 13px;
}
.greet-lead {
  margin-top: 14px;
  color: #606266;
  font-size: 14px;
}
.greet-lead:empty {
  display: none;
}
.sys-name {
  color: #c0c4cc;
  font-size: 12px;
  white-space: nowrap;
}

/* ---- 主行动区: 一大一小 ---- */
.cta-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 16px;
}
.cta-main,
.cta-sub {
  border-radius: 10px;
  padding: 18px 20px;
  min-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  cursor: pointer;
  transition: transform 0.15s ease;
}
.cta-main:hover,
.cta-sub:hover {
  transform: translateY(-2px);
}
.cta-main {
  background: #409eff;
  color: #fff;
}
.cta-sub {
  background: #f5f7fa;
  color: #303133;
  border: 0.5px solid #e4e7ed;
}
.cta-title {
  font-size: 16px;
  font-weight: 600;
}
.cta-desc {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
}
.cta-main .cta-desc {
  color: #d9ecff;
}
.cta-sub .cta-desc {
  color: #909399;
}
.cta-go {
  font-size: 13px;
}
.cta-go-light {
  color: #fff;
}
.cta-sub .cta-go {
  color: #409eff;
}

/* ---- 快捷入口: 图标卡片 ---- */
.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.shortcut-card {
  background: #fff;
  border: 0.5px solid #e4e7ed;
  border-radius: 10px;
  padding: 14px 12px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.shortcut-card:hover {
  border-color: #409eff;
}
.shortcut-icon {
  width: 38px;
  height: 38px;
  margin: 0 auto;
  border-radius: 8px;
  background: #ecf5ff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.shortcut-label {
  margin-top: 8px;
  font-size: 13px;
  color: #303133;
}

/* ---- 底部轻数据 ---- */
.foot-row {
  margin-top: 16px;
  padding: 12px 20px;
  background: #fafafa;
  border-radius: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #909399;
}
.foot-link {
  color: #409eff;
  cursor: pointer;
}

/* 窄屏降级: 主行动区与快捷入口改单列/两列 */
@media (max-width: 768px) {
  .cta-grid {
    grid-template-columns: 1fr;
  }
  .shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
