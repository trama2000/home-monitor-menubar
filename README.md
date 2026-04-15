# 🏠 Home Monitor - macOS Menu Bar App

App para la barra de menu de macOS que muestra datos en tiempo real de:

- ☀️ **Solarman** - Generacion solar, consumo, bateria
- 🔥 **ROTEX/Daikin** - Temperatura ACS, modo calefaccion, boost
- 🚗 **Tesla** - Bateria, estado de carga, temperatura interior

## Vista en la barra de menu

```
☀️7.4kW 🏠5.5kW 🔋92% 🚗52% 🌡️48.5°
```

Al hacer clic se despliega el menu completo con todos los datos.

## Instalacion

### Opcion 1: Ejecutar directamente (Python)

```bash
# Instalar dependencias
pip3 install -r requirements.txt

# Configurar credenciales
cp config_template.json ~/.home_monitor_config.json
nano ~/.home_monitor_config.json  # Editar con tus datos

# Ejecutar
python3 home_monitor.py
```

### Opcion 2: Crear app nativa (.app)

```bash
# Instalar dependencias
pip3 install -r requirements.txt

# Construir .app
python3 setup.py py2app

# La app se crea en dist/Home Monitor.app
# Arrastrala a /Applications
cp -r "dist/Home Monitor.app" /Applications/
```

### Arranque automatico

Para que se ejecute al iniciar sesion:
1. Abre **Preferencias del Sistema** > **General** > **Items de inicio**
2. Anade **Home Monitor** a la lista

## Configuracion

Edita `~/.home_monitor_config.json` con tus credenciales:

| Servicio | Datos necesarios |
|----------|-----------------|
| Solarman | email + password, o token preconfigurado |
| ROTEX | username + password de daikin-control.com |
| Tesla | access_token, refresh_token, client_id, client_secret, VIN |

### Intervalos de polling

- **Solarman**: cada 60 segundos
- **ROTEX**: cada 60 segundos  
- **Tesla**: cada 5 minutos (para no despertar el coche)

## Datos mostrados

### Barra de menu (resumen)
`☀️ Generacion  🏠 Consumo  🔋 Bateria Solar  🚗 Bateria Tesla  🌡️ ACS`

### Menu desplegable (detalle)

**☀️ SOLAR**
- Generacion (kW)
- Consumo casa (kW)
- Bateria solar (%)
- Excedente (kW)
- Carga/Descarga bateria (kW)
- Red (kW)

**🔥 CALEFACCION**
- Modo (Calefaccion/Verano/Standby/Refrigeracion)
- ACS temperatura actual vs objetivo
- Boost ACS (Si/No)
- Temperatura caldera
- Temperatura exterior

**🚗 TESLA**
- Bateria (%)
- Estado de carga
- Temperatura interior
- Cerrado/Abierto
- Sentry Mode

## Requisitos

- macOS 10.14+
- Python 3.8+
- Conexion a internet
