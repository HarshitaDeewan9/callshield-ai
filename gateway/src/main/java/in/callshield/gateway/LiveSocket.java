package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.net.http.WebSocket;
import java.nio.ByteBuffer;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.*;
@Component
public class LiveSocket extends AbstractWebSocketHandler {
    final AiClient ai; final RecordService saved; final ObjectMapper json;
    final ConcurrentHashMap<String,Bridge> bridges=new ConcurrentHashMap<>();
    public LiveSocket(AiClient a,RecordService s,ObjectMapper j){ai=a;saved=s;json=j;}
    boolean active(String recordId){return bridges.values().stream().anyMatch(b->b.record.id.equals(recordId));}
    static class Bridge {
        org.springframework.web.socket.WebSocketSession browser;
        volatile WebSocket upstream;
        volatile boolean finished=false;
        CompletableFuture<?> queue=CompletableFuture.completedFuture(null);
        com.fasterxml.jackson.databind.node.ArrayNode history=new ObjectMapper().createArrayNode();
        AnalysisRecord record;
        StringBuilder incoming=new StringBuilder(),transcript=new StringBuilder();
        AtomicInteger pending=new AtomicInteger();
    }
    @Override public void afterConnectionEstablished(org.springframework.web.socket.WebSocketSession socket) throws Exception {
        if(socket.getPrincipal()==null){socket.close(CloseStatus.POLICY_VIOLATION);return;}
        String id=socket.getUri().getPath().substring(socket.getUri().getPath().lastIndexOf('/')+1);
        Bridge b=new Bridge();b.record=saved.owned(id,saved.owner(socket.getPrincipal()));
        if(!b.record.kind.equals("LIVE")){socket.close(CloseStatus.POLICY_VIOLATION);return;}
        b.browser=new ConcurrentWebSocketSessionDecorator(socket,5000,65536);
        bridges.put(socket.getId(),b);
        try {
            b.upstream=ai.http.newWebSocketBuilder().connectTimeout(java.time.Duration.ofSeconds(10)).header("X-API-Key",ai.key)
                .buildAsync(ai.socketUri(id),new WebSocket.Listener(){
                    public void onOpen(WebSocket ws){b.upstream=ws;ws.request(1);}
                    public CompletionStage<?> onText(WebSocket ws,CharSequence data,boolean last) {
                        b.incoming.append(data);
                        if(b.incoming.length()>65536){ws.abort();close(b);return null;}
                        if(last){String message=b.incoming.toString();b.incoming.setLength(0);
                            try {
                                JsonNode event=json.readTree(message);String type=event.path("type").asText();
                                if(type.equals("transcript")){if(b.transcript.length()<200000)b.transcript.append(event.path("turn").path("speaker").asText("unknown")).append(": ").append(event.path("turn").path("text").asText()).append('\n');}
                                if(type.equals("risk")){b.history.add(json.createObjectNode().put("score",event.path("assessment").path("score").asInt()).put("revision",event.path("assessedRevision").asInt()));if(b.history.size()>100)b.history.remove(0);}
                                if(type.equals("closed"))b.finished=true;
                                if(type.equals("risk")||type.equals("closed")){
                                    ((ObjectNode)event).set("history",b.history.deepCopy());
                                    ((ObjectNode)event).put("originalTranscript",b.transcript.toString());
                                    b.record.payload=event.toString();saved.records.save(b.record);
                                }
                                if(b.browser.isOpen())b.browser.sendMessage(new TextMessage(message));
                            }catch(Exception ignored){ws.abort();close(b);}
                        }
                        ws.request(1);return CompletableFuture.completedFuture(null);
                    }
                    public CompletionStage<?> onClose(WebSocket ws,int status,String reason){close(b);return CompletableFuture.completedFuture(null);}
                    public void onError(WebSocket ws,Throwable error){close(b);}
                }).get(12,TimeUnit.SECONDS);
        }catch(Exception e){
            if(b.browser.isOpen())b.browser.sendMessage(new TextMessage("{\"type\":\"error\",\"code\":\"AI_UNAVAILABLE\",\"message\":\"Live analysis is unavailable. Start a new session.\"}"));
            close(b);
        }
    }
    @Override protected void handleTextMessage(org.springframework.web.socket.WebSocketSession socket,TextMessage message) throws Exception {
        Bridge b=bridges.get(socket.getId());if(b==null||b.upstream==null)return;
        if(message.getPayloadLength()>8192){close(b);return;}
        forward(b,()->b.upstream.sendText(message.getPayload(),true));
    }
    @Override protected void handleBinaryMessage(org.springframework.web.socket.WebSocketSession socket,BinaryMessage message) throws Exception {
        Bridge b=bridges.get(socket.getId());if(b==null||b.upstream==null)return;
        if(message.getPayloadLength()!=1024){close(b);return;}
        ByteBuffer copy=ByteBuffer.allocate(1024);copy.put(message.getPayload()).flip();
        forward(b,()->b.upstream.sendBinary(copy,true));
    }
    private void forward(Bridge b,java.util.function.Supplier<CompletableFuture<WebSocket>> send){
        synchronized(b){
            if(b.pending.incrementAndGet()>16){b.pending.decrementAndGet();b.upstream.abort();close(b);return;}
            b.queue=b.queue.thenCompose(ignored->send.get()).whenComplete((value,error)->{b.pending.decrementAndGet();if(error!=null)close(b);});
        }
    }
    private void close(Bridge b){
        if(!b.finished){
            b.finished=true;
            try{JsonNode last=saved.payload(b.record);if(last instanceof ObjectNode object){object.put("stale",true).put("status","INTERRUPTED");b.record.payload=object.toString();saved.records.save(b.record);}}catch(Exception ignored){}
        }
        try{if(b.browser.isOpen())b.browser.close(CloseStatus.NORMAL);}catch(Exception ignored){}
    }
    @Override public void afterConnectionClosed(org.springframework.web.socket.WebSocketSession socket,CloseStatus status){
        Bridge b=bridges.remove(socket.getId());if(b!=null){close(b);if(b.upstream!=null){synchronized(b){b.queue.handle((v,e)->null).thenCompose(v->b.upstream.sendClose(WebSocket.NORMAL_CLOSURE,"client disconnected"));}}}
    }
    @Override public void handleTransportError(org.springframework.web.socket.WebSocketSession socket,Throwable exception){Bridge b=bridges.get(socket.getId());if(b!=null)close(b);}
}
