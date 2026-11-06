package in.callshield.gateway;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.socket.config.annotation.*;
@Configuration @EnableWebSocket
public class SocketConfig implements WebSocketConfigurer {
    final LiveSocket handler; final String origin;
    public SocketConfig(LiveSocket handler,@Value("${callshield.public-origin}") String origin){this.handler=handler;this.origin=origin;}
    @Override public void registerWebSocketHandlers(WebSocketHandlerRegistry registry){
        String[] allowed=(origin.equals("http://localhost:5173")||origin.equals("http://127.0.0.1:5173"))?new String[]{"http://localhost:5173","http://127.0.0.1:5173"}:new String[]{origin};
        registry.addHandler(handler,"/ws/live/*").setAllowedOrigins(allowed);
    }
}
