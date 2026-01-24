# Universal Intercom - Setup & Testing Guide

## Overview
This guide covers setting up and testing the LiveKit-based Universal Intercom feature locally using Docker and Ngrok.

---

## Prerequisites
- Docker installed
- Ngrok account & CLI installed (`brew install ngrok`)
- Node.js 18+
- Python 3.10+

---

## Part 1: Backend Setup

### 1.1 Install Dependencies
```bash
cd /Users/apple/workspace/fastapi/WayFind_backend
pip install -r requirements.txt
```

### 1.2 Configure Environment
Add to your `.env` file:
```env
# LiveKit Configuration
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

### 1.3 Start Backend
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Part 2: LiveKit Server (Docker)

### 2.1 Start LiveKit Locally
```bash
docker run --rm \
    -p 7880:7880 \
    -p 7881:7881 \
    -p 7882:7882/udp \
    -e LIVEKIT_KEYS="devkey: secret" \
    livekit/livekit-server --dev --bind 0.0.0.0
```

**Important:** The key format must be `"key: secret"` with a space after the colon!


### 2.2 Expose via Ngrok (for mobile testing)
Since mobile devices can't access `localhost`, expose LiveKit:

```bash
ngrok http 7880
```

Note the HTTPS URL (e.g., `https://abc123.ngrok-free.app`).

**Update your `.env`:**
```env
LIVEKIT_URL=wss://abc123.ngrok-free.app  # Use wss:// for production
```

---

## Part 3: Frontend Setup

### 3.1 Install LiveKit Dependencies
```bash
cd /Users/apple/workspace/reactnative/WayFind_frontend
npm install @livekit/react-native @livekit/react-native-webrtc
```

### 3.2 Update app.json
Add the config plugin:
```json
{
  "expo": {
    "plugins": [
      "@livekit/react-native-webrtc"
    ]
  }
}
```

### 3.3 Build Custom Dev Client
**Important**: LiveKit uses native WebRTC modules that don't work in Expo Go.

```bash
# Install EAS CLI if not already
npm install -g eas-cli

# Login to Expo
eas login

# Build development client for Android
eas build --profile development --platform android

# Or for iOS
eas build --profile development --platform ios
```

Install the resulting APK/IPA on your device.

---

## Part 4: Testing the Feature

### 4.1 API Testing (Backend)
Test the endpoints directly:

**Get Intercom Token:**
```bash
curl -X GET "http://localhost:8000/v1/rides/{ride_id}/intercom/token" \
    -H "Authorization: Bearer {your_token}"
```

**Set Lead:**
```bash
curl -X POST "http://localhost:8000/v1/rides/{ride_id}/set-lead" \
    -H "Authorization: Bearer {your_token}" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "{target_user_id}"}'
```

**Get Intercom Status:**
```bash
curl -X GET "http://localhost:8000/v1/rides/{ride_id}/intercom/status" \
    -H "Authorization: Bearer {your_token}"
```

### 4.2 Frontend Testing
1. Start an active ride in the app
2. Navigate to the ride details screen
3. The IntercomBar should appear at the bottom
4. Tap to connect to the intercom

### 4.3 Multi-User Testing
1. **Device A (Lead)**: Set user as Lead via admin API
2. **Device A**: Join intercom - should auto-enable mic
3. **Device B (Member)**: Join same ride's intercom
4. **Device B**: Should hear Device A's audio

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/rides/{ride_id}/intercom/token` | Get LiveKit connection token |
| GET | `/v1/rides/{ride_id}/intercom/status` | Get intercom status & Lead info |
| POST | `/v1/rides/{ride_id}/set-lead` | Set a participant as Lead (Admin) |
| POST | `/v1/rides/{ride_id}/remove-lead` | Remove current Lead (Admin) |

---

## Troubleshooting

### "Module not found" errors
The `@livekit/react-native` modules require a custom dev build. They won't work in Expo Go.

### Token generation fails
- Check `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` in `.env`
- Ensure LiveKit server is running

### Can't connect from mobile
- Ensure Ngrok is running and URL is updated in backend `.env`
- Use `wss://` (not `ws://`) for the Ngrok URL

### No audio received
- Check device volume
- Ensure Lead's microphone is enabled
- Check browser/app microphone permissions

---

## Production Considerations

1. **Use LiveKit Cloud**: For production, consider [LiveKit Cloud](https://livekit.io/) instead of self-hosting
2. **TURN servers**: Needed for NAT traversal in production
3. **Token expiry**: Currently 24h, reduce for production
4. **Rate limiting**: Add rate limits to token endpoint
5. **Reconnection**: Implement exponential backoff

---

## Files Created/Modified

### Backend
- `services/livekit_service.py` - LiveKit SDK wrapper
- `api/intercom_api.py` - API endpoints
- `api/main.py` - Router registration
- `requirements.txt` - Added livekit-api
- `example.env` - LiveKit config vars

### Frontend
- `src/apis/intercomService.js` - API calls
- `src/hooks/useIntercom.js` - Connection management hook
- `src/components/intercom/IntercomBar.jsx` - UI component
