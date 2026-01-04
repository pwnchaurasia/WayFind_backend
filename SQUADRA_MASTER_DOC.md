# 🏍️ Squadra Project - Master Design Document

> **Version:** 2.2 (Synced with Codebase)
> **Last Updated:** January 3, 2026
> **Tech Stack:** React Native (Expo), Python (FastAPI), PostgreSQL (PostGIS), Redis.

---

## 1. Project Overview & Immediate Goal
Squadra is a motorcycle riding platform.
**Current Mission:** Complete the "Digital Clubhouse" (Group Management) and the "Navigation Deck" (Map & Routing) before adding gamification layers.

### Core Tech Stack
* **Frontend:** React Native (Expo), NativeBase/UI Kit (Dark Mode + Electric Green `#39FF14`).
* **Backend:** Python FastAPI (SQLAlchemy Models).
* **Database:** PostgreSQL + **PostGIS** (Required immediately for location data).
* **Maps:** OpenStreetMap (via `react-native-maps`) + **OSRM** (for routing).

---

## 2. Phase 1: Critical Path (The "House") 🚨
*These features must be completed first to have a functional product.*

### 2.1 Group Management (The Digital Clubhouse)
* **Status:** Backend Tables exist (`Organization`, `OrganizationMember`). Frontend UI is incomplete.
* **Requirements:**
    * **Org Dashboard:** A screen showing Org Name, Logo, Member Count, and "Next Ride" card.
    * **Member List:** A scrollable list of members with their Role (`OrganizationRole`).
    * **Join Requests:** Admin view to Approve/Reject new users.
    * **Roles & Permissions:**
        * *Founder/Admin:* Can create rides, remove members, edit Org profile.
        * *Member:* Can view rides, join rides, view other profiles.

### 2.2 The Map Engine (The Navigation Deck)
* **Status:** Basic MapSelector exists. Needs Routing & Live Tracking.
* **Features:**
    * **Default Map:** OpenStreetMap (OSM) Tiles.
    * **Ride Creation UI:**
        * Users drop a "Start" pin and "End" pin (`RideCheckpoint` table).
        * **Intermediate Waypoints:** User can tap to add "Lunch Stop" or "Fuel" markers.
    * **Route Sculpting (Backend):**
        * Input: List of Lat/Lng coordinates.
        * Process: Send to OSRM (Open Source Routing Machine).
        * Output: A "Snapped" road geometry returned to the app to draw a green polyline.

### 2.3 Live Ride Session
* **Logic:**
    * **WebSocket:** Connect to `/ws/ride/{ride_id}`.
    * **Location:** Poll GPS every 3-5s.
    * **Visuals:** Show other `RideParticipant` users as "Dots" on the map. Color-code based on `ParticipantRole` (Lead/Sweep).

---

## 3. Database Schema Blueprint (Actual)
*This reflects the current `models.py` implementation.*

### 3.1 Core Users & Devices
* **`User`**: `id`, `name`, `phone_number`, `role` (UserRole).
* **`DeviceInfo`**: Tracks `device_id`, `fcm_token` (for push notifications).

### 3.2 Groups & Organizations
* **`Organization`**: `id`, `name`, `logo`, `is_active`.
* **`OrganizationMember`**: Link table with `role` (Founder/Admin/Member).
* **`UserRideInformation`**: Stores vehicle info (`make`, `model`, `license_plate`) linked to `User`.

### 3.3 Rides & Tracking
* **`Ride`**: `id`, `org_id`, `status` (Planned/Active), `scheduled_date`, `route_geometry` (To be added via PostGIS).
* **`RideCheckpoint`**: `id`, `ride_id`, `type` (Start/End/Stop), `lat`, `lng`.
* **`RideParticipant`**: `id`, `user_id`, `ride_id`, `role` (Lead/Sweep/Rider), `has_paid`.
* **`AttendanceRecord`**: `id`, `user_id`, `ride_id`, `status` (Present/Absent), `marked_by`.

---

## 4. Phase 2: Gamification (The "Paint") 🎨
*To be implemented ONLY after Phase 1 is stable.*

### 4.1 Scalable Badge System
* **Database Design:** Use JSON-based criteria.
* **Categories:**
    * **Milestones:** 1k, 5k, 10k miles.
    * **Conditions:** Rain Rider, Night Owl.
    * **Social:** Pack Leader (Led 10 rides).

### 4.2 Territory Control
* **Logic:** Hexagon-based map ownership.
* **Rankings:** Weekly/Monthly tables for individuals and Orgs based on `AttendanceRecord` stats.

---

## 5. Technical Specifications for AI Assistant (Antigravity)

### 5.1 API Endpoints to Prioritize
* `GET /organizations/{id}`: Returns Org details + Member count.
* `GET /organizations/{id}/members`: Returns list of `OrganizationMember` with User details.
* `POST /rides/create`: Accepts `checkpoints` list and creates a `Ride`.
* `POST /rides/{id}/join`: Creates a `RideParticipant` entry.

### 5.2 Implementation Prompts
**Prompt 1 (Org Detail Screen):**
> "Reference Master Doc Section 2.1. Create `OrganizationDetailScreen.js`. Fetch data from `GET /organizations/{id}`. Display the logo and name. Below, add a TabView for 'Rides' and 'Members'. In the Members tab, list users from `organization_members` table."

**Prompt 2 (Ride Creation):**
> "Reference Master Doc Section 2.2. Create `CreateRideScreen.js`. It needs a MapView. Allow user to tap map to add markers. Store these as an array of objects `{lat, lng, type}`. When saving, POST to `/rides` endpoint which saves them as `RideCheckpoint` entries."