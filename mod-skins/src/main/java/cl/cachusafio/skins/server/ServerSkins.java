package cl.cachusafio.skins.server;

import cl.cachusafio.skins.net.SkinData;
import cl.cachusafio.skins.net.SkinNetwork;
import com.mojang.logging.LogUtils;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.networking.v1.S2CPlayChannelEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import org.slf4j.Logger;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** Guarda en memoria la skin de cada jugador conectado y la reparte. */
public final class ServerSkins {
    private static final Logger LOG = LogUtils.getLogger();
    private static final Map<UUID, SkinData> SKINS = new ConcurrentHashMap<>();
    private static final Map<UUID, Long> LAST_UPLOAD = new ConcurrentHashMap<>();
    /** Skins de jugadores que todavía no prueban su PIN: se reparten recién al verificarse. */
    private static final Map<UUID, SkinData> HELD = new ConcurrentHashMap<>();
    private static final long MIN_INTERVAL_MS = 3_000;

    private ServerSkins() {}

    public static void register() {
        // las skins de los que ya están se mandan cuando el cliente anuncia que tiene el mod (antes no se le puede enviar)
        S2CPlayChannelEvents.REGISTER.register((handler, sender, server, channels) -> {
            if (!channels.contains(SkinNetwork.SYNC)) return;
            server.execute(() -> SKINS.forEach((id, data) -> SkinNetwork.sendSync(handler.player, id, data)));
        });
        ServerPlayConnectionEvents.DISCONNECT.register((handler, server) -> server.execute(() -> onLogout(server, handler.player)));
        ServerLifecycleEvents.SERVER_STOPPED.register(server -> {
            SKINS.clear();
            LAST_UPLOAD.clear();
            HELD.clear();
        });
    }

    public static void receive(ServerPlayer sender, SkinData data) {
        UUID id = sender.getUUID();
        if (!PinAuth.isVerified(sender)) {
            HELD.put(id, data); // nadie ve la skin de alguien que podría estar suplantando a otro
            return;
        }
        long now = System.currentTimeMillis();
        Long last = LAST_UPLOAD.get(id);
        if (last != null && now - last < MIN_INTERVAL_MS) return;
        LAST_UPLOAD.put(id, now);

        SKINS.put(id, data);
        LOG.info("skin de {} recibida ({} bytes, modelo {}, capa {})", sender.getGameProfile().getName(), data.png().length,
                data.slim() ? "slim" : "classic", data.hasCape() ? data.cape().substring(0, 8) : "-");
        broadcast(sender.server, id, data);
    }

    static void onVerified(ServerPlayer player) {
        SkinData held = HELD.remove(player.getUUID());
        if (held != null) receive(player, held);
    }

    private static void onLogout(MinecraftServer server, ServerPlayer player) {
        UUID id = player.getUUID();
        LAST_UPLOAD.remove(id);
        HELD.remove(id);
        if (SKINS.remove(id) != null) broadcast(server, id, null);
    }

    private static void broadcast(MinecraftServer server, UUID id, SkinData data) {
        for (ServerPlayer p : server.getPlayerList().getPlayers()) SkinNetwork.sendSync(p, id, data);
    }
}
