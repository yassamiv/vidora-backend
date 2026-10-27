VIDORA BACKEND - RENDER DEPLOYMENT STARTER

This backend is a starter deployment package. It supports YouTube/youtu.be URLs only.
Use it only for videos you own or have explicit permission to download. Follow applicable
copyright law and the source platform's terms. Public deployment can incur costs and be abused;
review quotas, rate limiting, and provider terms before sharing the site widely.

DEPLOY:
1. Upload these files to a new GitHub repository.
2. In Render, choose New > Blueprint and connect that repository (render.yaml is included).
3. Wait for the service to deploy. Open https://YOUR-SERVICE.onrender.com/health and confirm {"status":"ok"}.
4. In Render's Environment settings, set ALLOWED_ORIGINS to:
   https://silly-torrone-de4d6f.netlify.app
   (comma-separate any other exact frontend origins you control)
5. The frontend must be updated to call the deployed backend URL. This ZIP does not automatically
   change the currently published Netlify frontend.

IMPORTANT TECHNICAL NOTES:
- FFmpeg must be available on the Render host for MP3 conversion and high-quality MP4 merging.
  This starter uses a Python runtime; if FFmpeg is not preinstalled on the selected host, use a
  Docker-based Render service with FFmpeg installed.
- Free hosting can sleep, time out, or have limited temporary disk space. Large downloads may fail.
- Do not expose a public downloader widely without request limits, authentication or abuse controls.
