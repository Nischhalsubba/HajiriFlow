# HajiriFlow portrait media

HajiriFlow uses a curated set of photographic portraits served from `images.unsplash.com` for employee records that do not yet have an uploaded profile photo.

## License

The portraits are used under the Unsplash License, which permits free commercial and non-commercial use, copying, modification, and distribution. Attribution is appreciated but not required.

Official license: https://unsplash.com/license

## Product behavior

1. An employee-uploaded photo takes priority.
2. When no uploaded photo exists, HajiriFlow assigns a stable licensed portrait from the curated pool.
3. If the external portrait cannot load, initials remain visible.
4. Uploaded profile photos are cropped to a square and compressed before storage.

## Production migration note

The current frontend stores uploaded profile photos in browser storage. Before multi-user production rollout, move employee photo storage to an authenticated object store such as Supabase Storage and persist the object path in the employee record.
