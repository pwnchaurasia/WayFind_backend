# SQUADRA Universal Intercom - Implementation Plan

## Overview
Implementing a LiveKit-based audio intercom for motorcycle riding groups (15+ riders).
**Audio Model**: Lead Broadcaster (1-to-many) - Lead Rider broadcasts, Members listen.

---

## Phase 1: Backend Implementation (FastAPI)

### 1.1 Database Changes
- **No schema changes needed** - `RideParticipant.role` already supports `LEAD` role
- Existing `ParticipantRole` enum: `RIDER`, `LEAD`, `MARSHAL`, `SWEEP`, `BANNED`

### 1.2 Dependencies
```bash
pip install livekit-api
```

### 1.3 Environment Variables
```env
LIVEKIT_URL=https://xxxx.livekit.cloud  # Or Ngrok URL for local dev
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

### 1.4 New API Endpoints

#### A. Token Generation Endpoint
```
GET /v1/rides/{ride_id}/intercom/token
```
- Returns LiveKit JWT token for connecting to room
- Lead gets `canPublish: true, canSubscribe: true`
- Members get `canPublish: false, canSubscribe: true`

#### B. Lead Assignment Endpoint
```
POST /v1/rides/{ride_id}/set-lead
Body: { "user_id": "uuid" }
```
- Only Org Admins can assign Lead
- Validates user is a participant
- Updates participant role to LEAD (demotes previous Lead to RIDER)

#### C. Get Intercom Status
```
GET /v1/rides/{ride_id}/intercom/status
```
- Returns who is current Lead
- Returns if intercom is available (ride must be ACTIVE)

### 1.5 Files to Create/Modify
1. `api/intercom_api.py` - New router for intercom endpoints
2. `services/livekit_service.py` - LiveKit SDK wrapper
3. `main.py` - Register new router
4. `requirements.txt` - Add livekit-api

---

## Phase 2: Frontend Implementation (React Native)

### 2.1 Dependencies
```bash
npm install @livekit/react-native @livekit/react-native-webrtc
```

### 2.2 Expo Config Plugins (app.json)
```json
{
  "plugins": [
    "@livekit/react-native-webrtc"
  ]
}
```

### 2.3 New Components/Hooks

#### A. `useIntercom` Hook
- Connects to LiveKit room
- Handles publishing (Lead) or subscribing (Member)
- Manages audio focus
- Auto-reconnects on network change

#### B. `IntercomBar` Component
- Floating UI showing intercom status
- Shows when Lead is speaking
- Volume controls
- SOS quick button

### 2.4 Files to Create
1. `src/services/intercomService.js` - API calls
2. `src/hooks/useIntercom.js` - LiveKit connection logic
3. `src/components/intercom/IntercomBar.jsx` - UI component
4. `src/components/intercom/IntercomProvider.jsx` - Context wrapper

---

## Phase 3: Local Testing Setup

### 3.1 Docker Command for LiveKit
```bash
docker run --rm -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
    -e LIVEKIT_KEYS="devkey:secret" \
    livekit/livekit-server --dev --bind 0.0.0.0
```

### 3.2 Ngrok Exposure
```bash
ngrok http 7880
```
Update `LIVEKIT_URL` in backend `.env` to Ngrok URL.

### 3.3 Custom Dev Client
Since `react-native-webrtc` requires native modules:
```bash
eas build --profile development --platform android
```

---

## Acceptance Criteria
1. ✅ Admin can assign any participant as Lead via API
2. ✅ Lead joins ride → mic auto-enables
3. ✅ Member joins ride → hears Lead clearly
4. ✅ Audio continues when phone locked
5. ✅ Switching Lead mid-ride works seamlessly

---

## Implementation Order
1. Backend: Add livekit-api dependency
2. Backend: Create LiveKit service wrapper
3. Backend: Create intercom API endpoints
4. Backend: Test token generation locally
5. Frontend: Add LiveKit dependencies
6. Frontend: Create intercom hook
7. Frontend: Create UI components
8. Integration testing with Ngrok

---

## Notes
- Room naming: `ride_{ride_id}` for each active ride
- Token expiry: 24 hours (ride duration max)
- Lead role persists in database, intercom state is ephemeral
