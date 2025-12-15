FROM nginx:1.25.2-alpine

COPY nginx-docker.prod.conf /etc/nginx/conf.d/default.conf
COPY cert.crt /etc/ssl/cert.pem    
COPY key.crt /etc/ssl/key.pem
COPY .htpasswd /etc/ssl/.htpasswd

RUN echo vm.overcommit_memory = 1 > /etc/sysctl.conf

