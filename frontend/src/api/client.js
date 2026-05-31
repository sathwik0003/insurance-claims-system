import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE_URL || '/api'


const http = axios.create({
  baseURL: BASE,
  timeout: 360000, // 6 minutes in milliseconds
});

export default http;

// ── Claims ─────────────────────────────────────────────────────────────────

export async function submitClaim(formData) {
  const { data } = await http.post('/claims/submit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function evalClaim(payload) {
  const { data } = await http.post('/claims/eval', payload)
  return data
}

export async function getClaim(claimId) {
  const { data } = await http.get(`/claims/${claimId}`)
  return data
}

export async function getMemberClaims(memberId) {
  const { data } = await http.get(`/claims/member/${memberId}`)
  return data
}

// ── Members ────────────────────────────────────────────────────────────────

export async function getMember(memberId) {
  const { data } = await http.get(`/members/${memberId}`)
  return data
}

export async function listMembers() {
  const { data } = await http.get('/members/')
  return data
}

// ── Health ─────────────────────────────────────────────────────────────────

export async function getHealth() {
  const { data } = await http.get('/health')
  return data
}