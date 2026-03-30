/**
 * Firestore CRUD ヘルパー
 *
 * Firestore の `venues` コレクションに対して読み書きを行う。
 * 既存の型定義 (VenuePin, VenueCard, VenueDetail) をそのまま利用。
 */
import {
    collection,
    doc,
    getDocs,
    getDoc,
    setDoc,
} from 'firebase/firestore'
import { db } from './firebase'
import type { VenuePin, VenueCard, VenueDetail } from '../types/api'

const VENUES_COLLECTION = 'venues'

// ── Read ──────────────────────────────────────────────

/**
 * Firestore から全店舗のピンデータを取得する。
 * 各ドキュメントの `pin` フィールドに VenuePin を格納する前提。
 */
export async function getFirestorePins(): Promise<VenuePin[]> {
    const snap = await getDocs(collection(db, VENUES_COLLECTION))
    const pins: VenuePin[] = []
    snap.forEach((d) => {
        const data = d.data()
        if (data.pin) {
            pins.push(data.pin as VenuePin)
        }
    })
    return pins
}

/**
 * Firestore から全店舗のカードデータを取得する。
 * 各ドキュメントの `card` フィールドに VenueCard を格納する前提。
 */
export async function getFirestoreCards(): Promise<VenueCard[]> {
    const snap = await getDocs(collection(db, VENUES_COLLECTION))
    const cards: VenueCard[] = []
    snap.forEach((d) => {
        const data = d.data()
        if (data.card) {
            cards.push(data.card as VenueCard)
        }
    })
    return cards
}

/**
 * Firestore から特定店舗の詳細データを取得する。
 * ドキュメントの `detail` フィールドに VenueDetail を格納する前提。
 */
export async function getFirestoreVenueDetail(id: string): Promise<VenueDetail | null> {
    const docRef = doc(db, VENUES_COLLECTION, id)
    const snap = await getDoc(docRef)
    if (!snap.exists()) return null
    const data = snap.data()
    return (data.detail as VenueDetail) ?? null
}

// ── Write ─────────────────────────────────────────────

/**
 * 単一店舗データを Firestore に書き込む（upsert）。
 * pin / card / detail の3形式をまとめて格納する。
 */
export async function upsertVenue(
    pin: VenuePin,
    card: VenueCard,
    detail: VenueDetail,
): Promise<void> {
    const docRef = doc(db, VENUES_COLLECTION, pin.id)
    await setDoc(docRef, { pin, card, detail }, { merge: true })
}
