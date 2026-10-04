<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'

const lofts = ref([])
const loading = ref(false)
const error = ref('')
const savingId = ref(null)
const savedId = ref(null)

// 每间一份可编辑草稿；已用数字始终以服务端回显为准，不本地推算
const drafts = reactive({})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/lofts/')
    lofts.value = data.results || data
    for (const loft of lofts.value) {
      if (!drafts[loft.id]) {
        drafts[loft.id] = {
          enabled: loft.capEnabled ?? false,
          limit: loft.capLimit ?? 10,
        }
      }
    }
  } catch {
    error.value = '封顶设置加载失败'
  } finally {
    loading.value = false
  }
}

async function save(loft) {
  const draft = drafts[loft.id]
  const limit = Number(draft.limit)
  if (!Number.isInteger(limit) || limit < 0) {
    error.value = `「${loft.name}」封顶数字必须是不小于 0 的整数`
    return
  }
  error.value = ''
  savingId.value = loft.id
  savedId.value = null
  try {
    await api.patch(`/lofts/${loft.id}/cap/`, {
      enabled: !!draft.enabled,
      limit,
    })
    savedId.value = loft.id
    await load()
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.limit?.[0] ||
      data?.enabled?.[0] ||
      data?.detail ||
      '封顶设置保存失败'
  } finally {
    savingId.value = null
  }
}

function usageOf(loft) {
  // 服务端口径：当天该间新插入的浸渍条数
  return loft.capUsedToday ?? 0
}

function isFull(loft) {
  const draft = drafts[loft.id]
  return draft?.enabled && usageOf(loft) >= Number(draft.limit)
}

onMounted(load)
</script>

<template>
  <div class="caps-page">
    <header class="caps-head">
      <div>
        <h1>日条数封顶</h1>
        <p class="sub">
          按帆布间设置当天允许新登记浸渍的条数。改卷态、标已固化不占封顶；
          「已用」按右侧面板当天实际写入条数统计，由后端实时给出。
        </p>
      </div>
      <button class="btn secondary" type="button" :disabled="loading" @click="load">刷新已用</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="loading && !lofts.length" class="hint">加载中…</div>
    <div v-else-if="!lofts.length" class="hint">尚无帆布间</div>

    <div class="cap-grid">
      <section v-for="loft in lofts" :key="loft.id" class="cap-card panel">
        <header class="cap-card-head">
          <div>
            <h2>{{ loft.name }}</h2>
            <p class="hint">{{ loft.location || '工位' }}</p>
          </div>
          <span class="badge" :class="drafts[loft.id]?.enabled ? 'badge-dipping' : 'badge-raw'">
            {{ drafts[loft.id]?.enabled ? '封顶启用中' : '未启用' }}
          </span>
        </header>

        <div class="cap-usage">
          <div class="cap-usage-num" :class="{ 'is-full': isFull(loft) }">
            {{ usageOf(loft) }}
            <small>/ {{ drafts[loft.id] ? drafts[loft.id].limit : loft.capLimit }}</small>
          </div>
          <p class="hint">
            今日已新登记浸渍条数
            <span v-if="isFull(loft)" class="error">（已满，新登记会被挡下）</span>
          </p>
        </div>

        <form class="cap-form" @submit.prevent="save(loft)">
          <label class="cap-check">
            <input v-model="drafts[loft.id].enabled" type="checkbox" />
            启用日条数封顶
          </label>
          <label>每天封顶条数
            <input
              v-model.number="drafts[loft.id].limit"
              type="number"
              min="0"
              step="1"
              required
            />
          </label>
          <div class="cap-actions">
            <button class="btn" type="submit" :disabled="savingId === loft.id">
              {{ savingId === loft.id ? '保存中…' : '保存设置' }}
            </button>
            <span v-if="savedId === loft.id" class="ok">已生效</span>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>
