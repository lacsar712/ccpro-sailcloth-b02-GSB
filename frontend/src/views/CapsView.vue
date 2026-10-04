<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const rows = ref([])
const error = ref('')
const notice = ref('')
const loading = ref(false)

async function load() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await api.get('/caps/')
    rows.value = (data.results || data).map((r) => ({
      ...r,
      draftCap: r.dailyCap,
      draftEnabled: r.enabled,
      saving: false,
    }))
  } catch {
    error.value = '日条数封顶配置加载失败'
  } finally {
    loading.value = false
  }
}

function dirty(row) {
  return Number(row.draftCap) !== row.dailyCap || row.draftEnabled !== row.enabled
}

function stateOf(row) {
  if (!row.enabled) return { key: 'off', label: '已停用' }
  if (row.remainingToday === 0) return { key: 'full', label: '今日已满' }
  return { key: 'open', label: '可登记' }
}

async function save(row) {
  error.value = ''
  notice.value = ''
  row.saving = true
  try {
    await api.patch(`/caps/${row.id}/`, {
      dailyCap: Number(row.draftCap),
      enabled: row.draftEnabled,
    })
    notice.value = row.draftEnabled
      ? `已保存「${row.loftName}」：今日新登记浸渍封顶 ${row.draftCap} 条`
      : `已保存「${row.loftName}」：封顶已停用，今日可继续登记`
    await load()
  } catch (e) {
    const data = e.response?.data
    error.value = data?.dailyCap?.[0] || data?.detail || '保存封顶配置失败'
  } finally {
    row.saving = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>日条数封顶</h1>
    <p class="sub">
      按帆布间限制当天允许新登记浸渍的条数。「今日已用」= 当天该间新插入的浸渍条数（晾晒架右侧面板写入即计入）；
      改卷态、标已固化不占条数。到顶后再登会被拒绝；停用后可继续登记。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>启用封顶</th>
          <th>日条数封顶</th>
          <th>今日已用</th>
          <th>今日剩余</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>
            <input v-model="row.draftEnabled" type="checkbox" class="cap-check" />
          </td>
          <td>
            <input
              v-model.number="row.draftCap"
              type="number"
              min="1"
              step="1"
              class="cap-input"
              :disabled="!row.draftEnabled"
            />
          </td>
          <td>{{ row.usedToday }}</td>
          <td>{{ row.enabled ? row.remainingToday : '—' }}</td>
          <td>
            <span class="badge" :class="'cap-' + stateOf(row).key">{{ stateOf(row).label }}</span>
          </td>
          <td>
            <button
              class="btn"
              type="button"
              :disabled="row.saving || !dirty(row)"
              @click="save(row)"
            >
              {{ row.saving ? '保存中…' : '保存' }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length && !loading">
          <td colspan="7" class="hint">暂无帆布间</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
