# Deployment 

Flask is a WSGI application which is run on a WSGI server. When a HTTP request reaches the server, these get transalted into the standard WSGI environ and outgoing WSGI responses get converted back into HTTP.

## Preamble 
A network interface is a point at which the machine can connect to the network. Each interface gets its own IP address. It is this address that other machines can send requests to. Some interfaces probably running on your laptop right now:
- Wifi interface with a real IP. This is how other devices can reach you via your router.
- A loopback interface - this is the `localhost` that your browser sometimes uses. This is an entirely virtual interface and nothing external to your machine can reach it. 

A server within a data center works the same way as your laptop, with a publically routable IP address on its external interface. 

A machine has a single IP address but many 'ports' within which to recieve traffic. If the IP address is a street address, then the port is the flat number. The ports on your computer are just represented by numbers from `0` to `65535`. Some ports are reserved for special purposes:
- `80` is the port for HTTP 
- `443` is the port for HTTPS - if you want to make a HTTPS request to a server, you must go via this port
    - When you type `https://google.com`, your browser looks up Google's IP address and opens a connection to that IP on port 443. Google's server is sitting there, listening and waiting for that connection.
- `22` is the port for SSH  
- `5432` is the port for PostgreSQL
Most of these are only 'reserved' in name, its just convention. The major exception is ports below 1024, which are enforced by the OS as privileged (more on this below). For the others, its just what we use to define defaults, and what people generally expect. 

When we just run a flask dev app, it listens on port `5000`. To reach it, go to  `http://localhost:5000` in a browser. When you type this in, your browser opens a connection (`127.0.0.1`) to port 5000 via the loopback interface. Any requests you send from the browser get handled by the flask app. 

Every process that is run on your machine is run by a user account. When you run the `uv run flask --app site/app run`, the python process is just owned by your login account. It inherits your permissions (such as reading and writing). 
- `root` is a special account that has permission to do everything 
- Running anything with `sudo` temporarily grants root powers 
It is only via `root` that you can tell an app to listen on a privileged port 

## Gunicorn

Gunicorn is a pure-Python WSGI server with simple configuration and support for multiple worker processes. Multiple workers allow it to handle multiple requests concurrently.

Gunicorn runs your app:
```sh
gunicorn "app:create_app()" --bind 0.0.0.0:8000
```


By default, the app listens on port `8000` of the gunicorn server. Note: `0.0.0.0` is not a port - it is a host address meaning "all network interfaces"

To bind at privelaged ports, we can use a reverse proxy. We want to bind at privelaged ports in order to be able to listen out for HTTP and HTTPS requests. We can run Gunicorn at root to do this, but this is a massive security risk - the application should not have read/write privelages over our entire computer. Instead, we put a reverse proxy in front of it. A reverse proxy is a server which sits in front of the Gunicorn server and forwards incoming requests to it. This way, the browser never directly interacts with Gunicorn, it sends HTTP(S) requests to the reverse proxy on ports `80`/`443`. The proxy forwards these internally to Gunicorn on `8000`. The browser has no idea that Gunicorn or the Flask application it is running exist.

```
Browser
  │  port 443
  ▼
Nginx (reverse proxy)
  │  port 8000
  ▼
Gunicorn → Flask app
```

## NGIX

`ngix` is an example of a reverse proxy. It can do things like:
- handle SSL/TLS - this is the encryption layer that makes HTTPS work. You can send encrypted requests to a browser. These can't be intercepted. Gunicorn itself won't know anything about encryption. It will continue to recieve plain HTTP internally.
- It can serve static files directly without the request ever reaching python.

## Telling Flask it is behind a proxy

When NGINX forwards a request to GUNICORN, flask sees a request from nginx (a local address) rather than the real client. This matters for things like URL generation (e.g. generating `http://` instead of `https://` because it thinks requests are local). 

Flask solves this using `ProxyFix` middleware, added into `create_app()`

## Getting a VPS

A VPS is a machine that we will rent and then SSH into. When we set up an NGINX web server, this means renting out a VPS and installing and configuring everything directly onto that machien. We would then communicate with this machine using SSH on our laptop 

```
Your laptop  ──SSH──►  VPS (Ubuntu machine)
                         │
                         ├── nginx        (installed as a system package)
                         ├── gunicorn     (running your Flask app)
                         ├── your code    (cloned from git)
                         └── systemd      (keeps gunicorn alive/restarts it)
```