FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# VITE_API_BASE_URL rỗng -> Frontend gọi API cùng-origin qua đường dẫn tương đối,
# nhưng ở đây ta build sẵn để trỏ sang API_DOMAIN thật (Caddy biên xử lý HTTPS/domain riêng)
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
RUN printf ":80 {\n\troot * /srv\n\tencode gzip\n\ttry_files {path} /index.html\n\tfile_server\n}\n" > /etc/caddy/Caddyfile
