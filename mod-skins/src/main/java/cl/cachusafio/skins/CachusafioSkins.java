package cl.cachusafio.skins;

import cl.cachusafio.skins.net.SkinNetwork;
import cl.cachusafio.skins.server.PinAuth;
import cl.cachusafio.skins.server.ServerSkins;
import net.fabricmc.api.ModInitializer;

/**
 * El launcher guarda la skin y la capa elegidas en {@code <juego>/cachusafio/}.
 * Al entrar a un mundo el cliente las envía al servidor, que las reparte a
 * todos los conectados; cada cliente las pinta sobre el jugador correspondiente.
 *
 * Versión Fabric del mod de Forge (modpack-cachusafio/mod-skins): mismo comportamiento y mismos archivos.
 */
public class CachusafioSkins implements ModInitializer {
    public static final String MOD_ID = "cachusafio_skins";

    @Override
    public void onInitialize() {
        SkinsConfig.load();
        SkinNetwork.registerServer();
        ServerSkins.register();
        PinAuth.register();
    }
}
