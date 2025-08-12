import java.util.*;
import java.util.concurrent.*;
import java.text.SimpleDateFormat;
import java.sql.Timestamp;

public class OrderService {
    // Simulating a cache that never evicts entries - common memory leak pattern
    private static final Map<String, Order> orderCache = new ConcurrentHashMap<>();
    private static final Random random = new Random();
    private static final SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    static class Order {
        String orderId;
        String customerId;
        List<OrderItem> items;
        byte[] metadata; // Large metadata object
        Timestamp createdAt;

        Order(String orderId, String customerId) {
            this.orderId = orderId;
            this.customerId = customerId;
            this.items = new ArrayList<>();
            this.createdAt = new Timestamp(System.currentTimeMillis());
            // Simulate large order metadata (photos, documents, etc.)
            this.metadata = new byte[1024 * 1024]; // 1MB per order
            random.nextBytes(this.metadata);
        }
    }

    static class OrderItem {
        String productId;
        int quantity;
        double price;

        OrderItem(String productId, int quantity, double price) {
            this.productId = productId;
            this.quantity = quantity;
            this.price = price;
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("[" + dateFormat.format(new Date()) + "] Order Service v2.1.0 starting...");
        System.out.println("[" + dateFormat.format(new Date()) + "] Initializing order processing system");

        // Simulate order processing
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(2);

        // Process new orders every 100ms
        executor.scheduleAtFixedRate(() -> {
            try {
                processNewOrder();
            } catch (Exception e) {
                System.err.println("[" + dateFormat.format(new Date()) + "] ERROR: Failed to process order: " + e.getMessage());
            }
        }, 0, 100, TimeUnit.MILLISECONDS);

        // Log statistics every 5 seconds
        executor.scheduleAtFixedRate(() -> {
            logStatistics();
        }, 5, 5, TimeUnit.SECONDS);

        // API endpoint simulation
        System.out.println("[" + dateFormat.format(new Date()) + "] REST API listening on port 8080");

        // Keep running
        Thread.currentThread().join();
    }

    private static void processNewOrder() {
        String orderId = "ORD-" + UUID.randomUUID().toString().substring(0, 8);
        String customerId = "CUST-" + random.nextInt(10000);

        Order order = new Order(orderId, customerId);

        // Add random items
        int itemCount = random.nextInt(5) + 1;
        for (int i = 0; i < itemCount; i++) {
            order.items.add(new OrderItem(
                "PROD-" + random.nextInt(1000),
                random.nextInt(10) + 1,
                random.nextDouble() * 100
            ));
        }

        // MEMORY LEAK: Orders are added but never removed from cache
        orderCache.put(orderId, order);

        // Simulate successful order processing
        if (random.nextDouble() > 0.98) { // 2% error rate
            System.err.println("[" + dateFormat.format(new Date()) + "] ERROR: Payment gateway timeout for order " + orderId);
        } else if (orderCache.size() % 100 == 0) {
            System.out.println("[" + dateFormat.format(new Date()) + "] INFO: Processed order " + orderId + " for customer " + customerId);
        }
    }

    private static void logStatistics() {
        Runtime runtime = Runtime.getRuntime();
        long usedMemory = (runtime.totalMemory() - runtime.freeMemory()) / 1024 / 1024;
        long maxMemory = runtime.maxMemory() / 1024 / 1024;

        System.out.println("[" + dateFormat.format(new Date()) + "] STATS: Orders in cache: " + orderCache.size() +
                         ", Memory: " + usedMemory + "MB/" + maxMemory + "MB" +
                         ", Threads: " + Thread.activeCount());

        // Warn when memory usage is high
        if (usedMemory > maxMemory * 0.8) {
            System.err.println("[" + dateFormat.format(new Date()) + "] WARN: High memory usage detected: " +
                             (usedMemory * 100 / maxMemory) + "%");
        }
    }
}
