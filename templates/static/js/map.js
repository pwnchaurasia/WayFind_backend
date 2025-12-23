// Nominatim Geocoding (FREE - OpenStreetMap)
class MapService {
    constructor() {
        this.nominatimUrl = 'https://nominatim.openstreetmap.org';
    }

    async searchAddress(query) {
        try {
            const response = await fetch(
                `${this.nominatimUrl}/search?q=${encodeURIComponent(query)}&format=json&limit=5`
            );
            const data = await response.json();
            return data.map(item => ({
                display_name: item.display_name,
                lat: parseFloat(item.lat),
                lon: parseFloat(item.lon),
                address: item.display_name
            }));
        } catch (error) {
            console.error('Geocoding error:', error);
            return [];
        }
    }

    async reverseGeocode(lat, lon) {
        try {
            const response = await fetch(
                `${this.nominatimUrl}/reverse?lat=${lat}&lon=${lon}&format=json`
            );
            const data = await response.json();
            return data.display_name;
        } catch (error) {
            console.error('Reverse geocoding error:', error);
            return '';
        }
    }

    async getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation not supported'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                position => resolve({
                    lat: position.coords.latitude,
                    lon: position.coords.longitude
                }),
                error => reject(error)
            );
        });
    }
}

const mapService = new MapService();