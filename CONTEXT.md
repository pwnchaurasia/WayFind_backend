# Squadra Project - Task Tracker (Mindmap)

> Last Updated: 2025-12-31

---

## Architecture Overview

### Role System (Confirmed)

| Layer | Roles | Description |
|-------|-------|-------------|
| **App-Level** | `SUPER_ADMIN`, `NORMAL_USER` | Super Admin has full system access |
| **Organization** | `FOUNDER`, `CO_FOUNDER`, `ADMIN` | Org-level permissions |
| **Ride Participant** | `RIDER`, `LEAD`, `MARSHAL`, `SWEEP` | Ride-specific roles |

> **Confirmed:** All users have a personal profile regardless of their org/admin roles.

### Current Frontend Tabs
- Home (index)
- Community (organizations) 
- Rides
- Profile (settings) ← **Currently placeholder**

---

## Completed Tasks ✅
### Rebranding (WayFind → Squadra) 🎨
- [x] App Name updated in `app.json` (Squadra)
- [x] Backend Templates (`users.html`, `rides.html`) updated
- [x] Email notifications updated
- [x] User-Agent strings updated to `Squadra-App/1.0`
- [x] Privacy/Terms text updated

### Deep Linking System 🔗
- [x] **Universal Links implemented**: `https://squadra.app/join/...`
- [x] **Custom Scheme**: `squadra://` matches `https` paths
- [x] **Web Fallback Pages**:
  - `join_ride.html`: Redirects to app or Play Store
  - `join_org.html`: Redirects to app or Play Store
- [x] **Ngrok Support**:
  - Added `ngrok-skip-browser-warning` header to Axios
  - Configured Templates to use `squadra://squadra.app/join/...` for robust routing

### Authentication & Permissions
- [x] Phone Login with OTP flow
- [x] **Fixed Redirect Loop**: `VerifyOTP` → `UpdateProfile` → `Dashboard`
- [x] **Location Permissions**: Added `ACCESS_BACKGROUND_LOCATION` to `app.json`
- [x] Token storage & Auth Context

### UI/UX
- [x] Login page (Phone + Google buttons)
- [x] Update profile with vehicle fields
- [x] Organization list view
- [x] **Profile Tab Complete**:
- [x] Vehicle Management (Add/Edit/Delete) with Limit (3)
- Edit Profile Mode vs Setup Mode
- Settings Menu

---

## Technical Configuration ⚙️

### Deep Linking Setup
- **Scheme**: `squadra://`
- **Host**: `squadra.app` (Placeholder for Universal Links)
- **Routes**:
  - `/join/ride/[id]`: Opens Ride Details
  - `/join/org/[code]`: Opens Org Join Invite
- **Testing**: Open `https://<NGROK>/join/ride/<ID>` → Click "Open in App".

### Ngrok Demo Setup
1. Backend: Expose port 8000 via Ngrok.
2. Frontend `.env`: Set `EXPO_PUBLIC_API_BASE_URL_DEV` to Ngrok URL.
3. **Important**: Restart Metro (`npx expo start --clear`) after `.env` changes.

---

## In Progress 🔄

### Map Provider
- [x] MapSelector component created with OSM + Google toggle
- [x] **Default to OpenStreetMap** ✅ Changed from Google

### Phase 1: Essential Launch Features 📱
- [ ] Live GPS tracking during rides
- [ ] Background location tracking (service implemented, pending UI)
- [ ] Push notifications (ride started, checkpoint nearby)


---

## Phase 1: Essential Launch Features 📱

### Mobile App Foundation
- [ ] Live GPS tracking during rides
- [ ] Background location tracking (battery optimized)
- [ ] Push notifications (ride started, checkpoint nearby)

### Safety & Legal
- [ ] Emergency SOS button
- [ ] Digital waiver/consent forms
- [ ] Emergency contact management
- [ ] Weather alerts for active rides

### Ride Experience
- [ ] Automatic check-in at checkpoints (GPS proximity)
- [ ] Real-time participant location on map (admin view)
- [ ] Ride start/end notifications
- [ ] Photo uploads at checkpoints

### Payment Integration
- [ ] Razorpay/PhonePe integration
- [ ] Online payment collection
- [ ] Payment receipt generation

---

## Phase 2: Operational Efficiency 🔧

### Admin Tools
- [ ] Bulk member import (CSV/Excel)
- [ ] Export reports (attendance, payments)
- [ ] Ride summary generation (PDF/Excel)
- [ ] Payment reconciliation dashboard

### Communication
- [ ] WhatsApp API integration
- [ ] Email notifications
- [ ] In-app chat
- [ ] Broadcast messages

### User Experience
- [ ] Offline mode (view past rides)
- [ ] Ride history with photos
- [ ] Profile management enhancements
- [ ] Notification preferences

---

## Immediate Action Items 🎯

1. **Change map default to OSM** in `MapSelector.js`
2. **Build Profile/Settings tab** with:
   - User profile display
   - Edit profile option
   - Vehicle management
   - Logout button
3. **Role-based dashboard views**:
   - Super Admin: All orgs, all users
   - Org Admin: Org management, member management
   - Rider: Personal rides, profile

---

## File References

| Component | Path |
|-----------|------|
| Map Selector | `src/components/map/MapSelector.js` |
| Settings Tab | `src/app/(main)/(tabs)/settings.js` |
| User Service | `src/apis/userService.js` |
| Auth Context | `src/context/AuthContext.js` |
| Backend Enums | `backend/utils/enums.py` |
| Backend User API | `backend/api/user_api.py` |
