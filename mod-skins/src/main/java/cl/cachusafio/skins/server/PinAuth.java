package cl.cachusafio.skins.server;

import cl.cachusafio.skins.SkinsConfig;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.logging.LogUtils;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.phys.Vec3;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.AttackBlockCallback;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.fabricmc.fabric.api.message.v1.ServerMessageEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;

import javax.annotation.Nullable;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;

/**
 * Protege los nombres en un servidor sin premium. El launcher manda una clave derivada del PIN del jugador
 * (nunca el PIN). La primera vez que un nombre entra, su clave queda registrada; después, quien entre con ese
 * nombre y otra clave es expulsado. Mientras se verifica (normalmente menos de un segundo) el jugador no puede
 * moverse, romper, poner, chatear ni recibir daño.
 *
 * Solo en servidores dedicados (en un mundo de un jugador no hace falta). PIN olvidado:
 * {@code /cachusafio pin reset <nombre>} (operadores).
 */
public final class PinAuth {
    private static final Logger LOG = LogUtils.getLogger();
    private static final Pattern TOKEN = Pattern.compile("[0-9a-f]{64}");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int MAX_FAILS = 5;
    private static final long LOCK_MS = 10 * 60_000L;

    private record Pending(long deadline, Vec3 pos, float yRot, float xRot) {}
    private record Stored(String salt, String hash) {}
    private static final class Fails { int count; long lockedUntil; }

    private static final Map<UUID, Pending> PENDING = new ConcurrentHashMap<>();
    private static final Set<UUID> VERIFIED = ConcurrentHashMap.newKeySet();
    private static final Map<String, Fails> FAILS = new ConcurrentHashMap<>();
    private static Map<String, Stored> store;
    private static boolean storeBroken;
    @Nullable private static MinecraftServer current;

    private PinAuth() {}

    private static Path file() {
        return FabricLoader.getInstance().getGameDir().resolve("cachusafio").resolve("pins.json");
    }

    private static boolean enabled(@Nullable MinecraftServer server) {
        return server != null && server.isDedicatedServer() && SkinsConfig.pinEnabled;
    }

    /** ¿Este jugador ya probó que es quien dice ser? (o el PIN está desactivado) */
    public static boolean isVerified(Player player) {
        return VERIFIED.contains(player.getUUID()) || !enabled(current);
    }

    /** También lo usa el mixin de comandos: mientras se verifica no se puede usar ninguno. */
    public static boolean isPending(@Nullable Object entity) {
        return entity instanceof ServerPlayer p && PENDING.containsKey(p.getUUID());
    }

    private static String key(ServerPlayer p) {
        return p.getGameProfile().getName().toLowerCase(Locale.ROOT);
    }

    /* ------------------------------------------------------------------ almacenamiento */

    /** null si pins.json está dañado: en ese caso nadie entra (mejor eso que dejar los nombres sin proteger). */
    @Nullable
    private static synchronized Map<String, Stored> store() {
        if (store != null || storeBroken) return store;
        try {
            Map<String, Stored> loaded = new HashMap<>();
            if (Files.isRegularFile(file())) {
                Map<String, Stored> m = GSON.fromJson(Files.readString(file(), StandardCharsets.UTF_8),
                        new TypeToken<Map<String, Stored>>() {}.getType());
                if (m != null) loaded.putAll(m);
            }
            store = loaded;
        } catch (Exception e) {
            storeBroken = true;
            LOG.error("No se pudo leer {}: nadie podrá entrar hasta que se arregle o se borre (y reinicies)", file(), e);
        }
        return store;
    }

    private static synchronized void save() {
        try {
            Files.createDirectories(file().getParent());
            Path tmp = file().resolveSibling("pins.json.tmp");
            Files.writeString(tmp, GSON.toJson(store), StandardCharsets.UTF_8);
            Files.move(tmp, file(), java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception e) {
            LOG.error("No se pudo guardar {}", file(), e);
        }
    }

    private static byte[] derive(String token, byte[] salt) {
        try {
            PBEKeySpec spec = new PBEKeySpec(token.toCharArray(), salt, 20_000, 256);
            return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static Stored hashNew(String token) {
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        Base64.Encoder b64 = Base64.getEncoder();
        return new Stored(b64.encodeToString(salt), b64.encodeToString(derive(token, salt)));
    }

    private static boolean matches(Stored s, String token) {
        Base64.Decoder b64 = Base64.getDecoder();
        return MessageDigest.isEqual(b64.decode(s.hash()), derive(token, b64.decode(s.salt())));
    }

    /* ------------------------------------------------------------------ verificación */

    /** Llega el paquete del cliente con su clave (cadena vacía si no tiene). Hilo principal del servidor. */
    public static void receive(ServerPlayer player, String token) {
        UUID id = player.getUUID();
        if (!PENDING.containsKey(id)) return; // ya verificado, o PIN desactivado
        String name = key(player);

        Fails f = FAILS.get(name);
        long now = System.currentTimeMillis();
        if (f != null && f.lockedUntil > now) {
            long min = Math.max(1, (f.lockedUntil - now + 59_999) / 60_000);
            kick(player, "Demasiados intentos con un PIN incorrecto. Prueba de nuevo en " + min + " min.");
            return;
        }
        if (!TOKEN.matcher(token).matches()) {
            kick(player, "Este servidor pide un PIN. Entra con el launcher de Cachusafio.");
            return;
        }

        Map<String, Stored> pins = store();
        if (pins == null) {
            kick(player, "El servidor tiene un problema con los PIN guardados. Avisa a un admin.");
            return;
        }
        Stored s = pins.get(name);
        if (s == null) {
            synchronized (PinAuth.class) { pins.put(name, hashNew(token)); }
            save();
            LOG.info("PIN registrado para {}", player.getGameProfile().getName());
            accept(player);
            player.sendSystemMessage(Component.literal("§aTu PIN quedó registrado: desde ahora nadie más puede entrar con tu nombre."));
        } else if (matches(s, token)) {
            FAILS.remove(name);
            accept(player);
        } else {
            Fails fails = FAILS.computeIfAbsent(name, k -> new Fails());
            if (++fails.count >= MAX_FAILS) {
                fails.count = 0;
                fails.lockedUntil = now + LOCK_MS;
            }
            LOG.warn("PIN incorrecto para {} ({})", player.getGameProfile().getName(), player.getIpAddress());
            kick(player, "PIN incorrecto. Si lo olvidaste, pídele a un admin que lo reinicie.");
        }
    }

    private static void accept(ServerPlayer player) {
        PENDING.remove(player.getUUID());
        VERIFIED.add(player.getUUID());
        ServerSkins.onVerified(player);
    }

    private static void kick(ServerPlayer player, String why) {
        PENDING.remove(player.getUUID());
        player.connection.disconnect(Component.literal(why));
    }

    /* ------------------------------------------------------------------ eventos */

    public static void register() {
        ServerLifecycleEvents.SERVER_STARTED.register(server -> current = server);
        ServerLifecycleEvents.SERVER_STOPPED.register(server -> {
            current = null;
            PENDING.clear();
            VERIFIED.clear();
        });
        // JOIN corre en el hilo del servidor: queda pendiente antes de que llegue cualquier paquete suyo
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> onLogin(handler.player));
        ServerPlayConnectionEvents.DISCONNECT.register((handler, server) -> {
            PENDING.remove(handler.player.getUUID());
            VERIFIED.remove(handler.player.getUUID());
        });
        ServerTickEvents.END_SERVER_TICK.register(PinAuth::onTick);

        // mientras se verifica no puede romper, poner, usar, pegar, chatear ni recibir daño (los comandos: ChatCommandMixin)
        PlayerBlockBreakEvents.BEFORE.register((level, player, pos, state, be) -> !isPending(player));
        UseBlockCallback.EVENT.register((player, level, hand, hit) -> isPending(player) ? InteractionResult.FAIL : InteractionResult.PASS);
        UseItemCallback.EVENT.register((player, level, hand) -> isPending(player) ? InteractionResultHolder.fail(player.getItemInHand(hand)) : InteractionResultHolder.pass(player.getItemInHand(hand)));
        AttackBlockCallback.EVENT.register((player, level, hand, pos, dir) -> isPending(player) ? InteractionResult.FAIL : InteractionResult.PASS);
        UseEntityCallback.EVENT.register((player, level, hand, entity, hit) -> isPending(player) ? InteractionResult.FAIL : InteractionResult.PASS);
        AttackEntityCallback.EVENT.register((player, level, hand, entity, hit) -> isPending(player) ? InteractionResult.FAIL : InteractionResult.PASS);
        ServerLivingEntityEvents.ALLOW_DAMAGE.register((entity, source, amount) -> !isPending(entity));
        ServerMessageEvents.ALLOW_CHAT_MESSAGE.register((message, sender, params) -> !isPending(sender));

        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> dispatcher.register(Commands.literal("cachusafio")
                .requires(src -> src.hasPermission(3))
                .then(Commands.literal("pin").then(Commands.literal("reset")
                        .then(Commands.argument("nombre", StringArgumentType.word()).executes(ctx -> {
                            String name = StringArgumentType.getString(ctx, "nombre").toLowerCase(Locale.ROOT);
                            Map<String, Stored> pins = store();
                            if (pins == null) {
                                ctx.getSource().sendFailure(Component.literal("pins.json está dañado; revisa el log del servidor."));
                                return 0;
                            }
                            boolean had;
                            synchronized (PinAuth.class) {
                                had = pins.remove(name) != null;
                                if (had) save();
                            }
                            FAILS.remove(name);
                            ctx.getSource().sendSuccess(() -> Component.literal(had
                                    ? "PIN de " + name + " borrado: la próxima vez que entre registra uno nuevo."
                                    : name + " no tenía PIN registrado."), true);
                            return had ? 1 : 0;
                        }))))));
    }

    private static void onLogin(ServerPlayer p) {
        if (!enabled(p.getServer())) return;
        long timeout = SkinsConfig.pinTimeoutSeconds * 1000L;
        PENDING.put(p.getUUID(), new Pending(System.currentTimeMillis() + timeout, p.position(), p.getYRot(), p.getXRot()));
    }

    private static void onTick(MinecraftServer server) {
        if (PENDING.isEmpty()) return;
        long now = System.currentTimeMillis();
        for (Map.Entry<UUID, Pending> e : PENDING.entrySet()) {
            ServerPlayer p = server.getPlayerList().getPlayer(e.getKey());
            if (p == null) continue;
            Pending w = e.getValue();
            if (now > w.deadline()) kick(p, "Este servidor pide un PIN. Entra con el launcher de Cachusafio.");
            else if (p.position().distanceToSqr(w.pos()) > 0.01) p.connection.teleport(w.pos().x, w.pos().y, w.pos().z, w.yRot(), w.xRot());
        }
    }
}
