/**
 * Runs once before the end-to-end tests, against the running stack (`docker compose up -d`).
 *
 * 1. waits until the API and the dashboard answer
 * 2. creates the test account e2e-admin (or resets it) with a new random password, through the API container, so no
 *    password is stored anywhere
 * 3. imports a port scan from a new attacker address (300 ports in 8 s, as a flow file) and waits for its alert
 *
 * The tests get the account and the attacker from E2E_USER, E2E_PASSWORD and E2E_ATTACKER (helpers.ts).
 */
import { execFileSync } from 'node:child_process'
import { randomBytes, randomInt } from 'node:crypto'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dirname, '../../..')
const API = process.env.E2E_API_URL ?? 'http://localhost:8000'
const DASHBOARD = process.env.E2E_BASE_URL ?? 'http://localhost:3000'
const USER = 'e2e-admin'

// Runs inside the API container, with the API's own password hashing and database settings.
const CREATE_USER = `
import os, uuid
import psycopg
from app.infrastructure.config import database_dsn
from app.infrastructure.security.password_hasher import Argon2PasswordHasher

name, password = os.environ["E2E_USER"], os.environ["E2E_PASSWORD"]
with psycopg.connect(database_dsn(), autocommit=True) as db:
    db.execute(
        "INSERT INTO users (user_id, username, password_hash, role) VALUES (%s, %s, %s, 'admin') "
        "ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, role = 'admin'",
        (uuid.uuid4(), name, Argon2PasswordHasher().hash(password)),
    )
`

function compose(args: string[], input?: string): string {
  return execFileSync('docker', ['compose', ...args], { cwd: ROOT, input, encoding: 'utf-8' })
}

async function waitFor<T>(what: string, check: () => Promise<T | undefined>, timeoutS: number): Promise<T> {
  const deadline = Date.now() + timeoutS * 1000
  while (Date.now() < deadline) {
    try {
      const value = await check()
      if (value !== undefined) return value
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
  throw new Error(`${what}: nothing after ${timeoutS} s. Is the stack running (docker compose up -d)?`)
}

/** The same scan as data/flows/scan-small.csv, but from `attacker` and at the current time. */
function writeScan(file: string, attacker: string): void {
  const start = Date.now() / 1000 - 30
  const rows = ['ts_start,duration_ms,src_ip,dst_ip,src_port,dst_port,protocol,packets,bytes,tcp_flags,label']
  for (let i = 0; i < 300; i++) {
    const ts = (start + (i * 8) / 300).toFixed(3)
    rows.push(`${ts},1.0,${attacker},10.0.0.5,${40000 + i},${1000 + i},TCP,1,60,S,port_scan`)
  }
  writeFileSync(file, rows.join('\n') + '\n')
}

export default async function globalSetup(): Promise<void> {
  await waitFor('API health', async () => ((await fetch(`${API}/health`)).ok ? true : undefined), 60)
  await waitFor('dashboard', async () => ((await fetch(DASHBOARD)).ok ? true : undefined), 60)

  const password = randomBytes(18).toString('base64url')
  compose(['exec', '-T', '-e', `E2E_USER=${USER}`, '-e', `E2E_PASSWORD=${password}`, 'api', 'python', '-'], CREATE_USER)
  const token = await waitFor<string>('login', async () => {
    const response = await fetch(`${API}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: USER, password }),
    })
    return response.ok ? (await response.json()).access_token : undefined
  }, 30)

  // a new address in every run, so an alert of an earlier run can't make a test pass
  const attacker = `10.77.${randomInt(1, 250)}.${randomInt(1, 250)}`
  const folder = `e2e-${randomBytes(4).toString('hex')}`
  mkdirSync(path.join(ROOT, 'data', 'tmp', folder), { recursive: true })
  try {
    writeScan(path.join(ROOT, 'data', 'tmp', folder, 'scan.csv'), attacker)
    const out = compose(['--profile', 'import', 'run', '--rm', '-T', '-e', `FLOW_FILE=/app/data/tmp/${folder}/scan.csv`, 'importer'])
    if (!out.includes('accepted=300 rejected=0')) throw new Error(`import failed:\n${out}`)
  } finally {
    rmSync(path.join(ROOT, 'data', 'tmp', folder), { recursive: true, force: true })
  }
  await waitFor(`alert for ${attacker}`, async () => {
    const response = await fetch(`${API}/api/v1/alerts?src_ip=${attacker}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return (await response.json()).items?.length ? true : undefined
  }, 90)

  process.env.E2E_USER = USER
  process.env.E2E_PASSWORD = password
  process.env.E2E_ATTACKER = attacker
}
