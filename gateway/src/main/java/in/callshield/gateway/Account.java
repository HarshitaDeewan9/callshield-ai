package in.callshield.gateway;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="accounts")
public class Account {
    @Id public String id;
    @Column(nullable=false,unique=true) public String email;
    @Column(name="display_name",nullable=false) public String displayName;
    @Column(name="password_hash",nullable=false) public String passwordHash;
    @Column(name="created_at",nullable=false) public Instant createdAt;
    protected Account() {}
    public Account(String email,String name,String hash) {
        id=UUID.randomUUID().toString(); this.email=email; displayName=name; passwordHash=hash; createdAt=Instant.now();
    }
}
