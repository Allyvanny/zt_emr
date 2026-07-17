(function () {
  if (sessionStorage.getItem('zt_loc_attempted')) return;
  sessionStorage.setItem('zt_loc_attempted', '1');
  if (!('geolocation' in navigator)) return;

  navigator.geolocation.getCurrentPosition(
    async function (pos) {
      try {
        const { latitude, longitude } = pos.coords;
        const res = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`);
        const geo = await res.json();
        const city = geo.city || geo.locality || '';
        const country = geo.countryName || '';
        if (!city && !country) return;
        await fetch('/auth/refine-location', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city, country })
        });
      } catch (e) {}
    },
    function () {},
    { timeout: 8000, maximumAge: 600000 }
  );
})();