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

## 5. Phase 3: Voice Communication (FUTURE) 🎙️
*Adding the "Discord-like" layer.*

### 5.1 Voice Channels
**Goal:** Seamless, low-latency voice chat for safety and coordination.
* **Channel Types:**
    * **All Riders:** General channel (default).
    * **Leads/Marshals:** Private command channel.
* **Interaction:**
    * **Push-to-Talk (PTT):** Big onscreen button for quick bursts.
    * **Always-On:** Noise-canceling open mic for leads (optional).

### 5.2 Technical Stack Proposals
* **Engine:** Agora.io or LiveKit (WebRTC).
* **Architecture:** Join voice room via `ride_id`.
* **UI:** Floating voice controls overlay map.

---

## 6. Implementation Prompts (For Antigravity)

### Prompt for Phase 2 (Map)
> "Reference Master Doc Section 4. Implement `LiveRideMap.js`. Use `react-native-maps`. Render the `riderLocations` from the `getLiveData` API as custom Markers with profile pictures. Draw a Polyline between ride checkpoints. Add a bottom sheet that shows the selected rider's details."

### Prompt for Phase 3 (Voice)
> "Reference Master Doc Section 5. Integrate Agora SDK. Create `VoiceControl.js` overlay. When user joins active ride, auto-join Agora channel `ride_{id}`. Implement PTT button logic."