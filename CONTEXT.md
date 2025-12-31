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

### Authentication
- [x] Phone Login with OTP flow
- [x] OTP verification screen
- [x] Token storage (SecureStore)
- [x] Auth context for session management
- [x] Profile update screen with vehicle info
- [x] Google Sign-In setup (requires dev build)

### Backend APIs
- [x] User authentication (OTP, Google)
- [x] User profile CRUD (`/users/me`)
- [x] Vehicle management (`/users/me/vehicles`)
- [x] Organization CRUD
- [x] Ride management
- [x] Member management with roles

### UI/UX
- [x] Login page (Phone + Google buttons)
- [x] Update profile with vehicle fields
- [x] Organization list view
- [x] Logo section component
- [x] App name updated to "Squadra"

---

## In Progress 🔄

### Map Provider
- [x] MapSelector component created with OSM + Google toggle
- [x] **Default to OpenStreetMap** ✅ Changed from Google

### Profile Tab
- [x] Profile tab implemented with full functionality ✅
- [x] Personal profile view (name, email, avatar)
- [x] Vehicle garage display
- [x] Settings menu (Notifications, Privacy, Help)
- [x] Logout functionality
- [x] Super Admin badge display

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
