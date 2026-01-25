# 🏍️ Squadra Project - Master Design Document

> **Version:** 3.0 (Major Release: Live Ride Phase 1 Complete)
> **Last Updated:** January 20, 2026
> **Tech Stack:** React Native (Expo), Python (FastAPI), PostgreSQL (PostGIS), Redis.

---

## 1. Project Overview & Status
Squadra is a motorcycle riding platform.
**Current State:**
- **Core Platform:** Complete (Org management, key roles, ride creation, deep linking).
- **Live Ride (Phase 1):** Complete (Auto attendance, location tracking, activity feed, SOS).
- **Next Mission:** Build the "Navigation Deck" (Real-time Map) and "Voice Comms" (Phase 3).

### Core Tech Stack
* **Frontend:** React Native (Expo), NativeBase/UI Kit (Dark Mode + Electric Green `#39FF14`).
* **Backend:** Python FastAPI (SQLAlchemy Models).
* **Database:** PostgreSQL + **PostGIS**.
* **Maps:** OpenStreetMap (via `react-native-maps`).
* **Background Tasks:** Expo TaskManager (Location tracking).

---

## 2. Phase 1: Critical Path (COMPLETED) ✅
*These foundational features are now live and production-ready.*

### 2.1 Core Infrastructure
* **Organization Management:** Create/Edit/Manage Orgs.
* **Role System:** Founder, Co-Founder, Admin, Member, Rider.
* **Deep Linking:** HTTPS links for viral ride sharing (`squadra.app/join/...`).
* **Ride Management:** Create rides with checkpoints (Meetup, Destination).

### 2.2 Live Ride System (Phase 1 Implemented)
* **Auto Check-in:**
    * **Logic:** Background location tracking + Haversine distance calc.
    * **Trigger:** User enters 100m radius of a checkpoint.
    * **Result:** Auto-marks `AttendanceRecord` as `present` & posts to activity feed.
* **Activity Feed (WhatsApp Style):**
    * **Events:** Arrivals, Ride Start/End, User Join/Left, SOS Alerts.
    * **UI:** Real-time feel via polling (15s interval).
    * **Alerts:** SOS, Low Fuel, Breakdown, Need Help.
* **Riders List:**
    * Shows all participants with "Present/Absent" status.
    * Live "Active Now" indicators based on location timestamps.

---

## 3. Database Schema Blueprint (Actual)
*Reflects current implementation including live ride features.*

### 3.1 Core Users & Groups
* **`User`**: `id`, `name`, `role`, `profile_picture`.
* **`Organization`**: `id`, `name`, `logo`, `join_code`.
* **`OrganizationMember`**: Link table (`user_id`, `org_id`, `role`).

### 3.2 Rides & Logistics
* **`Ride`**: `id`, `status` (Planned/Active/Completed), `started_at`, `ended_at`.
* **`RideCheckpoint`**: `id`, `type` (Meetup/Destination), `lat`, `lng`, `radius`.
* **`RideParticipant`**: `id`, `user_id`, `ride_id`, `role`.

### 3.3 Live Ride Data (NEW)
* **`AttendanceRecord`**: `id`, `user_id`, `checkpoint_type`, `status` (Present).
* **`RideActivity`**: 
    * `activity_type` (arrived_meetup, sos_alert, etc).
    * `message`, `checkpoint_id`, `created_at`.
* **`UserLocation`**: 
    * `latitude`, `longitude`, `speed`, `heading`, `accuracy`.
    * Stores historical track points for active rides.

---

## 4. Phase 2: The Map Engine (IN PROGRESS) 🚧
*The "Navigation Deck" transformation.*

### 4.1 Real-time Map Experience
**Goal:** A visually stunning map screen that serves as the command center.
* **Visuals:** Custom dark-mode map style.
* **Route Rendering:** Display the ride path (Polyline) connecting checkpoints.
* **Rider Markers:**
    * **Dynamic Markers:** Custom views showing User Profile Picture + Name Label.
    * **Heading Arrow:** Rotating cone indicating direction.
    * **Status Colors:** Green (Moving), Red (Stopped/SOS), Grey (Offline).
* **Interactions:**
    * **Tap Rider:** Show "call" or "navigate to" action sheet.
    * **Group Center:** Button to zoom fit all active riders.

### 4.2 Technical Plan
* **Frontend:** `react-native-maps` with custom `Marker` components.
* **Optimization:** Throttle marker updates to avoid jitter.
* **Navigation:** Integration with external apps (Google Maps) for turn-by-turn to a rider.

---

## 5. Phase 3: Voice Communication (IMPLEMENTED) 🎙️
*Universal Intercom - One-way broadcast from Lead to Members.*

### 5.1 Concept: Universal Intercom
**Goal:** Simple, one-way voice broadcast for ride coordination.
* **Lead (1 person):** Broadcasts voice to all riders.
* **Members (everyone else):** Listen only - no broadcast capability.
* **Use Case:** Lead can announce directions, hazards, stops without needing walkie-talkies.

### 5.2 Technical Implementation
* **Engine:** LiveKit (WebRTC) - `livekit-api` Python SDK for backend tokens.
* **API Endpoint:** `GET /v1/rides/{id}/intercom/token` - Returns JWT token with permissions.
* **Room Naming:** `ride_{uuid}` - One room per active ride.
* **Permissions:**
    * Lead: `can_publish=True, can_subscribe=True`
    * Members: `can_publish=False, can_subscribe=True`

### 5.3 UX Design Decisions (Jan 25, 2026)
**Location:** Intercom control lives in the **Live Ride screen header** (not a floating overlay).

| User Role | Icon | State | Color | Action |
|-----------|------|-------|-------|--------|
| **Lead** | `mic` | Broadcasting | Green border | Tap to mute/unmute |
| **Member (connected)** | `headphones` | Listening | Green border | Tap to disconnect |
| **Member (disconnected)** | `headphones` | Off | Gray | Tap to start listening |
| **Connecting** | spinner | - | Orange | - |

**Design Rationale:**
* ❌ NO floating overlay bars (were cutting off content).
* ❌ NO auto-connect (users opt-in by tapping the icon).
* ✅ Clean header icon next to SOS button.
* ✅ Visual feedback via border color and icon changes.

### 5.4 Backend Files
```
services/livekit_service.py     - Token generation, room management
api/intercom_api.py             - REST endpoints for intercom
```

### 5.5 Frontend Files
```
src/hooks/useIntercom.js                   - LiveKit connection hook
src/app/(main)/rides/[id]/live.jsx         - IntercomButton in header
src/components/intercom/IntercomBar.jsx    - DEPRECATED (not used)
```

### 5.6 Environment Variables Required
```
LIVEKIT_URL=ws://localhost:7880           # LiveKit server URL
LIVEKIT_API_KEY=devkey                    # API key
LIVEKIT_API_SECRET=secret                 # API secret
```

---

## 6. UI/UX Guidelines

### 6.1 Ride Details Page Layout
**Info Card Structure (Top to Bottom):**
1. **Title Row:** Ride name + Org name (left), Status badge (right)
2. **Meta Row:** Date, Ride Type, Payment amount
3. **Stats Row:** Joined / Spots Left / Max Riders
4. **Action Buttons Row:** Start Ride | End Ride | Live (horizontal, below stats)

**Header Icons:**
* Edit (if admin, ride not completed)
* Share (always visible)
* NO copy link icon (removed to reduce clutter)

### 6.2 Live Ride Screen Header
* Back button (left)
* "Live Ride" title + LIVE badge + Tracking indicator (center)
* Intercom button (right, before SOS)
* SOS button (far right)

---

## 7. Implementation Prompts (For Antigravity)

### Prompt for Phase 2 (Map)
> "Reference Master Doc Section 4. Implement `LiveRideMap.js`. Use `react-native-maps`. Render the `riderLocations` from the `getLiveData` API as custom Markers with profile pictures. Draw a Polyline between ride checkpoints. Add a bottom sheet that shows the selected rider's details."

### Prompt for Phase 3 (Voice) - DONE
> "Intercom is implemented via LiveKit. See Section 5. The IntercomButton component in live.jsx handles connection. useIntercom hook manages LiveKit room connection. Backend token generation in livekit_service.py."