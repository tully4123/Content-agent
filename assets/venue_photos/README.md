# Venue photo library

Drop real photos in here and `scripts/render_carousel.py` will pick from
them automatically when building carousel images - no filename has to
match a specific slide.

**Two ways to organise it, both work:**

- **Subfolders per venue** (recommended if you've got a lot of photos):
  ```
  assets/venue_photos/Heyday/bar-1.jpg
  assets/venue_photos/Heyday/bar-2.jpg
  assets/venue_photos/Illawarra Hotel/beer-garden.jpg
  ```
- **Descriptively named files in one folder:**
  ```
  assets/venue_photos/heyday_bar_1.jpg
  assets/venue_photos/illawarra_hotel_beer_garden.jpg
  ```

The renderer matches a slide's venue name against folder names and file
names by word overlap - "Heyday" matches a `Heyday/` folder or a
`heyday_bar_1.jpg` file either way. Name things the way you'd naturally
describe the venue and it'll find it.

Cover, payoff, and outro slides don't belong to one venue, so they get a
photo picked from the whole library instead (avoiding repeats within the
same carousel where possible).

If nothing in the library matches a slide, it falls back to a dark
placeholder with a note on what to shoot - so a build is always postable
as a mockup, and upgrades the moment a matching photo turns up here.

Photo files themselves aren't committed to git (see `.gitignore`) - only
this README and the folder itself. Keep your own backup of the originals.
