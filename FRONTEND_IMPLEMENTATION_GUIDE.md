# WayFind Frontend Implementation Guide

This document outlines the frontend changes needed to implement the new rides and organizations system, replacing the previous group-based architecture.

## Overview

The backend has been restructured to support:
- **Organizations**: Created by Super Admin, managed by Founder/Co-Founder/Admin hierarchy
- **Rides**: Created by organization admins, with meetup/destination/disbursement checkpoints
- **Users**: Can join rides as riders or pillions, with motorcycle information
- **Attendance**: Tracks user progress through ride checkpoints

## Key Changes from Groups to Organizations/Rides

### 1. User Roles

#### Application Level:
- **SUPER_ADMIN**: Only you (application owner)
- **NORMAL_USER**: Regular users

#### Organization Level:
- **FOUNDER**: Can manage organization, create rides, manage members
- **CO_FOUNDER**: Same permissions as Founder (co-owner)
- **ADMIN**: Can create and manage rides within organization

#### Ride Level:
- **RIDER**: Regular participant
- **LEAD**: Lead rider for the ride
- **MARSHAL**: Support rider, helps manage group
- **SWEEP**: Last rider, ensures no one is left behind

### 2. User Model Updates

```typescript
interface User {
  id: string;
  name: string;
  email: string;
  phone_number: string;
  is_email_verified: boolean;
  is_phone_verified: boolean;
  is_active: boolean;
  profile_picture_url: string;
  role: 'SUPER_ADMIN' | 'NORMAL_USER';
  
  created_at: string;
  updated_at: string;
  
  // Relationships
  ride_vehicles?: UserRideInformation[];
}
```

### 2.1. NEW: UserRideInformation Model

```typescript
interface UserRideInformation {
  id: string;
  user_id: string;
  make: string;
  model: string;
  year?: number;
  license_plate?: string;
  is_primary: boolean;  // User's primary vehicle
  is_pillion: boolean;  // For passengers
  created_at: string;
  updated_at: string;
  
  // Relationships
  user?: User;
  ride_participations?: RideParticipant[];
}
```

### 3. New Organization Model

```typescript
interface Organization {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  
  // Relationships (populated by API)
  rides?: Ride[];
  members?: OrganizationMember[];
}

interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  role: 'FOUNDER' | 'CO_FOUNDER' | 'ADMIN';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  
  // Populated relationships
  user?: User;
  organization?: Organization;
}
```

### 4. Ride Model Updates

```typescript
interface Ride {
  id: string;
  organization_id: string;
  name: string;
  status: 'PLANNED' | 'ACTIVE' | 'COMPLETED';
  max_riders: number; // Default 30
  created_at: string;
  started_at?: string;
  ended_at?: string;
  updated_at: string;
  
  // Relationships
  organization?: Organization;
  checkpoints?: RideCheckpoint[];
  participants?: RideParticipant[];
  attendance_records?: AttendanceRecord[];
}

interface RideCheckpoint {
  id: string;
  ride_id: string;
  type: 'MEETUP' | 'DESTINATION' | 'DISBURSEMENT';
  latitude: number;
  longitude: number;
  radius_meters: number; // Default 50
  created_at: string;
  updated_at: string;
  
  ride?: Ride;
}

interface RideParticipant {
  id: string;
  ride_id: string;
  user_id: string;
  role: 'RIDER' | 'LEAD' | 'MARSHAL' | 'SWEEP';
  registered_at: string;
  updated_at: string;
  
  ride?: Ride;
  user?: User;
}

interface AttendanceRecord {
  id: string;
  ride_id: string;
  user_id: string;
  checkpoint_type: 'MEETUP' | 'DESTINATION' | 'DISBURSEMENT';
  reached_at: string;
  latitude: number;
  longitude: number;
  distance_traveled_km?: number;
  created_at: string;
  updated_at: string;
  
  ride?: Ride;
  user?: User;
}
```

## Required Frontend Changes

### 1. Authentication & User Management

#### Update Registration Flow
- Add motorcycle information fields (make, model)
- Add pillion/rider selection
- Keep existing OTP verification for phone numbers

#### User Profile Updates
- Display motorcycle information
- Show organization memberships
- Show ride history

### 2. Super Admin Features (Only You)

#### Organization Management
```typescript
// API Endpoints to implement:
POST /api/organizations          // Create organization
GET /api/organizations           // List all organizations
PUT /api/organizations/:id      // Update organization
DELETE /api/organizations/:id   // Delete organization
```

#### Organization Member Management
```typescript
// Add members to organizations
POST /api/organizations/:id/members
{
  user_id: string;
  role: 'FOUNDER' | 'CO_FOUNDER' | 'ADMIN';
}

// List organization members
GET /api/organizations/:id/members

// Update member role (Founder/Co-Founder only)
PUT /api/organizations/:id/members/:member_id
{
  role: 'FOUNDER' | 'CO_FOUNDER' | 'ADMIN';
}
```

### 3. Organization Admin Features

#### Ride Management
```typescript
// Create ride with checkpoints
POST /api/rides
{
  organization_id: string;
  name: string;
  max_riders?: number;
  checkpoints: [
    {
      type: 'MEETUP' | 'DESTINATION' | 'DISBURSEMENT';
      latitude: number;
      longitude: number;
      radius_meters?: number;
    }
  ];
}

// List organization rides
GET /api/organizations/:id/rides

// Update ride
PUT /api/rides/:id
{
  name?: string;
  status?: 'PLANNED' | 'ACTIVE' | 'COMPLETED';
  max_riders?: number;
}

// Start/End ride
POST /api/rides/:id/start
POST /api/rides/:id/end
```

#### Ride Participants Management
```typescript
// List ride participants
GET /api/rides/:id/participants

// Update participant role
PUT /api/rides/:id/participants/:participant_id
{
  role: 'RIDER' | 'LEAD' | 'MARSHAL' | 'SWEEP';
}

// IMPORTANT: Only organization admins can see phone numbers
// Regular participants see only names and basic info
```

### 4. User Ride Features

#### Vehicle Management
```typescript
// Add vehicle to user's garage
POST /api/users/me/vehicles
{
  make: string;
  model: string;
  year?: number;
  license_plate?: string;
  is_primary: boolean;
  is_pillion: boolean;
}

// List user's vehicles
GET /api/users/me/vehicles
// Returns array of UserRideInformation

// Update vehicle
PUT /api/users/me/vehicles/:vehicle_id
{
  make?: string;
  model?: string;
  year?: number;
  license_plate?: string;
  is_primary?: boolean;
}

// Delete vehicle
DELETE /api/users/me/vehicles/:vehicle_id
```

#### Join Ride Flow
```typescript
// Generate join link
GET /api/rides/:id/join-link
// Returns: https://yourapp.com/join-ride/{ride_id}

// Join ride (after OTP verification)
POST /api/rides/:id/join
{
  phone_number: string;
  otp_code: string;
  vehicle_info_id?: string; // User selects which vehicle to use
  is_pillion?: boolean; // If joining as passenger
}
```

#### Ride History
```typescript
// Get user's ride history
GET /api/users/me/rides
// Returns all rides user participated in with attendance records

// Get specific ride details
GET /api/rides/:id
// Includes checkpoints, participants (limited info for non-admins)
```

#### Check-in System
```typescript
// Check in at checkpoint
POST /api/rides/:id/checkin
{
  checkpoint_type: 'MEETUP' | 'DESTINATION' | 'DISBURSEMENT';
  latitude: number;
  longitude: number;
}
```

### 5. UI/UX Changes Required

#### Navigation Updates
- Replace "Groups" with "Organizations"
- Add "Rides" section
- Keep "My Profile" but update with motorcycle info

#### Organization Management Screen (Super Admin)
- List all organizations
- Create/edit organization form
- Add/remove members with role selection
- Member role management (Founder/Co-Founder can't be changed by Admins)

#### Ride Management Screen (Organization Admins)
- Create ride form with checkpoint map
- Add multiple checkpoints (meetup, destination, disbursement)
- Set max riders limit
- Start/end ride controls
- Participant management with role assignment

#### Ride Join Screen (Users)
- Simple ride join with phone/OTP
- Motorcycle information collection for new users
- Pillion/rider selection

#### Active Ride Screen
- Map view with checkpoints
- Real-time participant locations
- Check-in buttons at checkpoints
- Distance tracking

#### Ride History Screen
- List of participated rides
- Attendance records per ride
- Distance traveled statistics

### 6. Permission Logic

#### Phone Number Visibility
```typescript
function canViewPhoneNumber(user: User, ride: Ride): boolean {
  return user.role === 'SUPER_ADMIN' || 
         isOrganizationAdmin(user, ride.organization_id);
}

function isOrganizationAdmin(user: User, orgId: string): boolean {
  return user.organization_memberships?.some(
    member => member.organization_id === orgId && 
    ['FOUNDER', 'CO_FOUNDER', 'ADMIN'].includes(member.role)
  );
}
```

#### Ride Management Permissions
```typescript
function canManageRide(user: User, ride: Ride): boolean {
  return user.role === 'SUPER_ADMIN' || 
         isOrganizationAdmin(user, ride.organization_id);
}

function canAssignRideRoles(user: User, ride: Ride): boolean {
  return isOrganizationAdmin(user, ride.organization_id);
}
```

### 7. API Response Updates

#### User Registration Response
```typescript
{
  user: User;
  message: "Registration successful";
  requires_otp: true;
}
```

#### Ride Join Response
```typescript
{
  participant: RideParticipant;
  ride: Ride;
  message: "Successfully joined ride";
}
```

#### Organization List Response (Super Admin)
```typescript
{
  organizations: Organization[];
  total: number;
}
```

### 8. Real-time Updates

#### WebSocket Events
```typescript
// Ride status changes
ride:status_changed
{
  ride_id: string;
  status: 'PLANNED' | 'ACTIVE' | 'COMPLETED';
}

// Participant location updates (during active rides)
ride:location_update
{
  ride_id: string;
  user_id: string;
  latitude: number;
  longitude: number;
}

// Checkpoint reached
ride:checkpoint_reached
{
  ride_id: string;
  user_id: string;
  checkpoint_type: string;
  timestamp: string;
}
```

## Migration Steps

### Phase 1: Backend Integration
1. Update API client with new endpoints
2. Update TypeScript interfaces
3. Implement authentication flow changes
4. Add organization management UI

### Phase 2: Core Features
1. Implement ride creation and management
2. Add ride join flow with OTP
3. Implement check-in system
4. Add ride history and statistics

### Phase 3: Advanced Features
1. Real-time location tracking
2. WebSocket integration
3. Maps and checkpoint visualization
4. Analytics and reporting

## Testing Considerations

### User Scenarios to Test
1. Super Admin creates organization and adds members
2. Organization Admin creates ride with checkpoints
3. User joins ride via link with OTP
4. Ride check-in at various checkpoints
5. Phone number visibility permissions
6. Role-based access controls

### Edge Cases
1. Ride exceeding max riders limit
2. Duplicate ride join attempts
3. Invalid OTP during join
4. Network issues during check-ins
5. Role permission boundary testing

## Notes

- All existing group-related features should be removed or migrated
- Phone number visibility is restricted to organization admins and super admins
- Motorcycle information is required for riders, optional for pillions
- OTP verification remains mandatory for phone number validation
- Real-time features are optional but recommended for better UX

This guide provides a comprehensive roadmap for implementing the new rides and organizations system in your frontend application.
