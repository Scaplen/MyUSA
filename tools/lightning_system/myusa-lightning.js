(function (global) {
  'use strict';

  const MILES_PER_METER = 0.000621371;

  function milesBetween(aLat, aLon, bLat, bLon) {
    const R = 3958.7613;
    const toRad = (d) => d * Math.PI / 180;
    const dLat = toRad(bLat - aLat);
    const dLon = toRad(bLon - aLon);
    const x = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }

  function ageMinutes(iso) {
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return null;
    return Math.max(0, (Date.now() - t) / 60000);
  }

  class MyUSALightning {
    constructor(options) {
      if (!global.L) throw new Error('Leaflet must be loaded before MyUSALightning');
      if (!options || !options.map) throw new Error('map is required');
      this.map = options.map;
      this.feedUrl = options.feedUrl || '/api/lightning';
      this.refreshMs = options.refreshMs || 60000;
      this.center = options.center || null;
      this.timer = null;
      this.flashLayer = global.L.layerGroup().addTo(this.map);
      this.ringLayer = global.L.layerGroup().addTo(this.map);
      this.enabled = true;
      this.drawRings();
    }

    setEnabled(enabled) {
      this.enabled = !!enabled;
      if (this.enabled) {
        this.flashLayer.addTo(this.map);
        this.ringLayer.addTo(this.map);
        this.refresh();
      } else {
        this.map.removeLayer(this.flashLayer);
        this.map.removeLayer(this.ringLayer);
      }
    }

    setCenter(lat, lon) {
      this.center = { lat: Number(lat), lon: Number(lon) };
      this.drawRings();
      if (this.enabled) this.refresh();
    }

    drawRings() {
      this.ringLayer.clearLayers();
      if (!this.center) return;
      [10, 20, 30].forEach((miles) => {
        const radius = miles / MILES_PER_METER;
        global.L.circle([this.center.lat, this.center.lon], {
          radius,
          color: '#ffffff',
          weight: 2,
          opacity: 0.85,
          fillOpacity: 0,
          interactive: false,
        }).addTo(this.ringLayer);
      });
    }

    markerStyle(age) {
      if (age == null) return { radius: 4, opacity: 0.65 };
      if (age <= 5) return { radius: 6, opacity: 1 };
      if (age <= 15) return { radius: 5, opacity: 0.85 };
      return { radius: 4, opacity: 0.55 };
    }

    async refresh() {
      if (!this.enabled) return;
      try {
        const url = new URL(this.feedUrl, global.location.href);
        url.searchParams.set('_', String(Date.now()));
        const res = await fetch(url.toString(), { cache: 'no-store' });
        if (!res.ok) throw new Error(`lightning feed ${res.status}`);
        const data = await res.json();
        const features = Array.isArray(data.features) ? data.features : [];
        this.render(features);
      } catch (err) {
        global.dispatchEvent(new CustomEvent('myusa:lightning-error', { detail: { error: String(err) } }));
      }
    }

    render(features) {
      this.flashLayer.clearLayers();
      let nearest = null;
      let nearestAge = null;
      let count30 = 0;

      features.forEach((f) => {
        if (!f || !f.geometry || f.geometry.type !== 'Point') return;
        const coords = f.geometry.coordinates || [];
        const lon = Number(coords[0]);
        const lat = Number(coords[1]);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        const age = ageMinutes(f.properties && f.properties.observed);
        if (age != null && age > 30.5) return;

        const style = this.markerStyle(age);
        const marker = global.L.circleMarker([lat, lon], {
          radius: style.radius,
          color: '#fff2a8',
          weight: 1,
          fillColor: '#ffd21f',
          fillOpacity: style.opacity,
        });
        marker.bindTooltip(`NOAA GOES lightning${age == null ? '' : ` · ${Math.round(age)} min ago`}`);
        marker.addTo(this.flashLayer);

        if (this.center) {
          const miles = milesBetween(this.center.lat, this.center.lon, lat, lon);
          if (miles <= 30) count30 += 1;
          if (nearest == null || miles < nearest) {
            nearest = miles;
            nearestAge = age;
          }
        }
      });

      const detail = {
        nearestMiles: nearest,
        nearestAgeMinutes: nearestAge,
        within10: nearest != null && nearest <= 10,
        within20: nearest != null && nearest <= 20,
        within30: nearest != null && nearest <= 30,
        count30,
        observedFeatureCount: features.length,
      };
      global.dispatchEvent(new CustomEvent('myusa:lightning-update', { detail }));
    }

    start() {
      this.stop();
      this.refresh();
      this.timer = global.setInterval(() => this.refresh(), this.refreshMs);
    }

    stop() {
      if (this.timer) global.clearInterval(this.timer);
      this.timer = null;
    }
  }

  global.MyUSALightning = MyUSALightning;
  global.MyUSALightningDistanceMiles = milesBetween;
})(window);
