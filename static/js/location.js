/* Zero Trust EMR — device-based location refinement.
   IP-geolocation (server-side) can never resolve private/LAN IPs like
   192.168.x.x or 127.0.0.1 — that's a hard networking limit, not a bug.
   This asks the BROWSER for its GPS coordinates, reverse-geocodes them to
   the most specific place possible (village / ward / street), and sends
   the result to the server for display only. Risk scoring is untouched. */
(function () {
  // Clear the flag on new logins so geolocation runs for each user
  const params = new URLSearchParams(window.location.search);
  if (params.has('new_session')) {
    sessionStorage.removeItem('zt_loc_attempted');
  }
  if (!sessionStorage.getItem('zt_loc_attempted')) {
    sessionStorage.setItem('zt_loc_attempted', '1');
    detectLocation();
  }

  // Expose manual refresh function
  window.refreshLocation = function () {
    const badge = document.querySelector('[data-location-display]');
    if (badge) badge.textContent = '🌍 Detecting location...';
    sessionStorage.removeItem('zt_loc_attempted');
    detectLocation();
  };

  function detectLocation() {
    if (!('geolocation' in navigator)) return;

    navigator.geolocation.getCurrentPosition(
      async function (pos) {
        try {
          const { latitude, longitude, accuracy } = pos.coords;

        // ── 1st attempt: Nominatim / OpenStreetMap (zoom=18 for max detail) ──
        let detailed = '';
        try {
          const r1 = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&zoom=18&addressdetails=1&extratags=1&namedetails=1`,
            { headers: { 'Accept-Language': 'en' } }
          );
          const geo = await r1.json();
          detailed = buildNominatimLocation(geo);
        } catch (_) { /* try fallback */ }

        // ── 2nd attempt: Nominatim at zoom=17 (ward/neighborhood level) ──────
        // If zoom=18 gave bad results (weird road names), try a slightly
        // lower zoom which tends to return more reliable place names.
        if (!detailed || hasBadRoadName(detailed)) {
          try {
            const r1b = await fetch(
              `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&zoom=17&addressdetails=1&extratags=1&namedetails=1`,
              { headers: { 'Accept-Language': 'en' } }
            );
            const geo = await r1b.json();
            const alt = buildNominatimLocation(geo);
            if (alt && (!detailed || alt.length > detailed.length)) {
              detailed = alt;
            }
          } catch (_) { /* ignore */ }
        }

        // ── 3rd attempt: BigDataCloud ──────────────────────────────────────
        if (!detailed || hasBadRoadName(detailed)) {
          try {
            const r2 = await fetch(
              `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`
            );
            const geo = await r2.json();
            const bdc = buildBDCLocation(geo);
            // Prefer BDC if it has better place names
            if (bdc && (!detailed || !hasBadRoadName(bdc))) {
              detailed = bdc;
            }
          } catch (_) { /* give up silently */ }
        }

        if (!detailed) return;

        // ── Final cleanup: remove any remaining junk ──
        detailed = cleanLocation(detailed);

        await fetch('/auth/refine-location', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ detailed: detailed })
        });

        const badge = document.querySelector('[data-location-display]');
        if (badge) badge.textContent = '🌍 ' + detailed;
      } catch (e) { /* silent — falls back to IP-based location already shown */ }
    },
    function (err) {
      /* Permission denied — try IP-based fallback display */
      console.warn('Geolocation denied:', err.message);
    },
    { timeout: 10000, maximumAge: 600000, enableHighAccuracy: true }
  );

  /* ── Check if a location string contains a bad/misleading road name ──── */
  function hasBadRoadName(loc) {
    if (!loc) return false;
    const lower = loc.toLowerCase();
    // Road names that are descriptions, not place names
    const badPatterns = [
      'shortcut', 'short cut', 'shotcut', 'road to', 'route to',
      'highway', 'motorway', 'towards', 'near ', 'beside',
      'next to', 'opposite', 'across from', 'turnoff', 'turn off',
      'junction', 'intersection', 'bypass'
    ];
    return badPatterns.some(p => lower.includes(p));
  }

  /* ── Nominatim / OpenStreetMap builder (smart prioritization) ─────────── */
  function buildNominatimLocation(geo) {
    const a = geo.address || {};
    const named = geo.namedetails || {};
    const extra = geo.extratags || {};

    // Skip useless generic names
    const skip = new Set(['africa', 'tanzania', 'united republic of tanzania',
      'asia', 'earth', 'unknown', '']);

    // ── Tier 1: Named places (most reliable) ──
    // These are actual named places from OSM, not derived from road names
    const placeName = named.name || named['name:en'] || '';
    if (placeName && !skip.has(placeName.toLowerCase()) && !hasBadRoadName(placeName)) {
      // We have a good named place — use it as the primary identifier
      return buildSmartCombo(a, placeName, skip);
    }

    // ── Tier 2: Administrative hierarchy (ward, village, etc.) ──
    // Prioritize meaningful place types over road names
    const priority = [
      a.hamlet, a.village, a.neighbourhood, a.quarter,
      a.suburb, a.ward, a.city_district, a.town, a.municipality
    ];

    const parts = [];
    const seen = new Set();

    // First pass: add priority place names (skip roads)
    for (const c of priority) {
      if (!c) continue;
      const key = c.toLowerCase().trim();
      if (seen.has(key) || skip.has(key)) continue;
      if (/^\d+$/.test(c.trim())) continue;
      if (hasBadRoadName(c)) continue;
      seen.add(key);
      parts.push(c.trim());
      if (parts.length >= 3) break;
    }

    // Second pass: add road/street name only if it looks real
    if (parts.length < 4) {
      const roads = [a.road, a.footway, a.path];
      for (const r of roads) {
        if (!r) continue;
        const key = r.toLowerCase().trim();
        if (seen.has(key) || skip.has(key)) continue;
        if (hasBadRoadName(r)) continue;
        if (/^\d+$/.test(r.trim())) continue;
        seen.add(key);
        parts.push(r.trim());
        if (parts.length >= 4) break;
      }
    }

    // Third pass: add city/district if room
    if (parts.length < 4) {
      const extras = [a.city, a.county, a.state_district, a.state, a.region];
      for (const e of extras) {
        if (!e) continue;
        const key = e.toLowerCase().trim();
        if (seen.has(key) || skip.has(key)) continue;
        seen.add(key);
        parts.push(e.trim());
        if (parts.length >= 4) break;
      }
    }

    return parts.join(', ');
  }

  /* ── Build smart combo when we have a named place + hierarchy ─────────── */
  function buildSmartCombo(a, placeName, skip) {
    const parts = [placeName];
    const seen = new Set([placeName.toLowerCase()]);

    // Add hierarchy after the place name
    const hierarchy = [
      a.hamlet, a.village, a.neighbourhood, a.ward,
      a.suburb, a.town, a.city, a.municipality,
      a.county, a.state_district, a.state
    ];

    for (const h of hierarchy) {
      if (!h) continue;
      const key = h.toLowerCase().trim();
      if (seen.has(key) || skip.has(key)) continue;
      if (hasBadRoadName(h)) continue;
      seen.add(key);
      parts.push(h.trim());
      if (parts.length >= 4) break;
    }

    return parts.join(', ');
  }

  /* ── BigDataCloud builder (fallback) ──────────────────────────────────── */
  function buildBDCLocation(geo) {
    const skip = new Set(['africa', 'tanzania', 'asia', 'earth', 'unknown', '']);
    const info = (geo.localityInfo && geo.localityInfo.informative) || [];
    const names = info
      .filter(x => x.order <= 5 && x.name && !skip.has(x.name.toLowerCase()))
      .map(x => x.name);

    const seen = new Set();
    return names
      .filter(n => { const k = n.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return !hasBadRoadName(n); })
      .slice(0, 4)
      .join(', ');
  }

  /* ── Final cleanup of location string ─────────────────────────────────── */
  function cleanLocation(loc) {
    if (!loc) return loc;
    // Remove leading/trailing commas and spaces
    loc = loc.replace(/^[\s,]+|[\s,]+$/g, '');
    // Remove "Shotcut to Library" and similar junk if they leaked through
    loc = loc.replace(/\bshortcut to \w+/gi, '').replace(/\bshotcut to \w+/gi, '');
    // Remove "Mbeya Municipal" if it appears after the ward (redundant)
    // Keep it only if it's the only geographic reference
    const parts = loc.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length >= 3) {
      const filtered = parts.filter(p => !p.toLowerCase().includes('municipal'));
      if (filtered.length >= 2) return filtered.join(', ');
    }
    return parts.join(', ');
  }
})();
