# Cachusafio Skins (Fabric 1.20.1)

Versión Fabric del mod de `modpack-cachusafio/mod-skins` (Forge). Mismo comportamiento y mismos archivos:
la skin y la capa del **Vestidor** del launcher se ven dentro del servidor, y cada nombre queda protegido
con el PIN del launcher.

- El launcher deja `cachusafio/skin.png` y `cachusafio/skin.json` en la carpeta del juego y pasa la clave
  del PIN en la variable de entorno `CACHUSAFIO_AUTH`.
- El servidor guarda los PIN en `cachusafio/pins.json`. PIN olvidado: `/cachusafio pin reset <nombre>` (operadores).
- Configuración: `config/cachusafio_skins.properties` (`activado`, `segundosParaVerificar`).
- Mientras se verifica el PIN el jugador no puede moverse, romper, usar cosas, pegar, chatear, usar comandos ni recibir daño.

**Tiene que estar en el servidor también** (carpeta `mods/` del servidor de Manhunt). Es opcional en ambos lados.

## Compilar

Necesita un JDK 17 completo (con `javac`):

```
JAVA_HOME=~/.gradle/jdks/temurin-17 ./gradlew build   # -> build/libs/cachusafio-skins-fabric-<versión>.jar
```

Prueba local: `./gradlew runServer --args=nogui` y luego
`CACHUSAFIO_AUTH=<64 hex> ./gradlew runClient -PtestJoin=localhost:25599 [-PtestName=Amigo]`
(el servidor usa `run/server.properties` con `online-mode=false` y `server-port=25599`).
