-- ============================================================
--  Energy Usage Monitoring System — MySQL Schema
--  Stack: React + FastAPI + MySQL
-- ============================================================

CREATE DATABASE IF NOT EXISTS energy_monitor;
USE energy_monitor;

-- ------------------------------------------------------------
-- 1. Building
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Building (
    building_id       INT AUTO_INCREMENT PRIMARY KEY,
    building_name     VARCHAR(100) NOT NULL,
    address           VARCHAR(255),
    city              VARCHAR(100),
    building_type     VARCHAR(50),
    total_floors      INT,
    construction_year YEAR
);

-- ------------------------------------------------------------
-- 2. Floor
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Floor (
    floor_id        INT AUTO_INCREMENT PRIMARY KEY,
    building_id     INT NOT NULL,
    floor_number    INT NOT NULL,
    number_of_rooms INT DEFAULT 0,
    FOREIGN KEY (building_id) REFERENCES Building(building_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 3. Room
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Room (
    room_id          INT AUTO_INCREMENT PRIMARY KEY,
    floor_id         INT NOT NULL,
    room_number      VARCHAR(20) NOT NULL,
    room_type        VARCHAR(50),
    area_sqft        DECIMAL(8,2),
    occupancy_status ENUM('occupied','vacant') DEFAULT 'vacant',
    FOREIGN KEY (floor_id) REFERENCES Floor(floor_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 4. User
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS User (
    user_id     INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    phone       VARCHAR(20),
    role        ENUM('admin','manager','resident') DEFAULT 'resident',
    password    VARCHAR(255) NOT NULL,   -- SHA-256 hex hash
    building_id INT,
    FOREIGN KEY (building_id) REFERENCES Building(building_id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- 5. Device
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Device (
    device_id          INT AUTO_INCREMENT PRIMARY KEY,
    room_id            INT NOT NULL,
    device_name        VARCHAR(100) NOT NULL,
    device_type        VARCHAR(50),
    power_rating_watts DECIMAL(8,2),
    installation_date  DATE,
    device_status      ENUM('active','inactive','faulty') DEFAULT 'active',
    FOREIGN KEY (room_id) REFERENCES Room(room_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 6. Sensor
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Sensor (
    sensor_id         INT AUTO_INCREMENT PRIMARY KEY,
    device_id         INT NOT NULL,
    sensor_type       VARCHAR(50),
    installation_date DATE,
    status            ENUM('online','offline','error') DEFAULT 'online',
    FOREIGN KEY (device_id) REFERENCES Device(device_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 7. Energy_Usage
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Energy_Usage (
    usage_id            INT AUTO_INCREMENT PRIMARY KEY,
    device_id           INT NOT NULL,
    sensor_id           INT,
    timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP,
    energy_consumed_kwh DECIMAL(10,4) NOT NULL,
    voltage             DECIMAL(7,2),
    current_ampere      DECIMAL(7,2),
    FOREIGN KEY (device_id) REFERENCES Device(device_id) ON DELETE CASCADE,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- 8. Alert
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Alert (
    alert_id        INT AUTO_INCREMENT PRIMARY KEY,
    device_id       INT NOT NULL,
    alert_type      VARCHAR(50),
    alert_message   TEXT,
    threshold_value DECIMAL(10,2),
    triggered_time  DATETIME DEFAULT CURRENT_TIMESTAMP,
    status          ENUM('active','resolved','dismissed') DEFAULT 'active',
    FOREIGN KEY (device_id) REFERENCES Device(device_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 9. Energy_Report
-- (UNIQUE on building_id + report_date so ON DUPLICATE KEY works)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Energy_Report (
    report_id                INT AUTO_INCREMENT PRIMARY KEY,
    building_id              INT NOT NULL,
    report_date              DATE NOT NULL,
    total_energy_kwh         DECIMAL(12,4),
    peak_usage_time          DATETIME,
    carbon_emission_estimate DECIMAL(10,4),
    UNIQUE KEY uq_building_date (building_id, report_date),
    FOREIGN KEY (building_id) REFERENCES Building(building_id) ON DELETE CASCADE
);

-- ============================================================
-- Seed data
-- ============================================================

INSERT INTO Building (building_id, building_name, address, city, building_type, total_floors, construction_year) VALUES
(1, 'EcoTower A',   '12 Green Ave',  'Chennai',   'Commercial',  10, 2018),
(2, 'SolarBlock B', '34 Watt Road',  'Bengaluru', 'Residential',  6, 2020)
ON DUPLICATE KEY UPDATE building_name = VALUES(building_name);

INSERT INTO Floor (floor_id, building_id, floor_number, number_of_rooms) VALUES
(1, 1, 1, 4),
(2, 1, 2, 4),
(3, 2, 1, 3)
ON DUPLICATE KEY UPDATE number_of_rooms = VALUES(number_of_rooms);

INSERT INTO Room (room_id, floor_id, room_number, room_type, area_sqft, occupancy_status) VALUES
(1, 1, '101', 'Office',      450.00, 'occupied'),
(2, 1, '102', 'Conference',  300.00, 'occupied'),
(3, 2, '201', 'Office',      450.00, 'vacant')
ON DUPLICATE KEY UPDATE room_type = VALUES(room_type);

-- Password for both users = "admin123"  (SHA-256)
INSERT INTO User (user_id, name, email, phone, role, password, building_id) VALUES
(1, 'Admin User', 'admin@ecotower.com', '9876543210', 'admin',    '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 1),
(2, 'Priya M',    'priya@ecotower.com', '9876543211', 'resident', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 1)
ON DUPLICATE KEY UPDATE password = VALUES(password);

INSERT INTO Device (device_id, room_id, device_name, device_type, power_rating_watts, installation_date, device_status) VALUES
(1, 1, 'Main AC Unit',   'AC',        1500.00, '2022-01-10', 'active'),
(2, 1, 'Ceiling Light',  'Light',       60.00, '2022-01-10', 'active'),
(3, 2, 'Projector',      'Appliance',  200.00, '2022-03-15', 'active')
ON DUPLICATE KEY UPDATE device_status = VALUES(device_status);

INSERT INTO Sensor (sensor_id, device_id, sensor_type, installation_date, status) VALUES
(1, 1, 'Energy Sensor', '2022-01-10', 'online'),
(2, 2, 'Energy Sensor', '2022-01-10', 'online')
ON DUPLICATE KEY UPDATE status = VALUES(status);

INSERT INTO Energy_Usage (device_id, sensor_id, timestamp, energy_consumed_kwh, voltage, current_ampere) VALUES
(1, 1, NOW() - INTERVAL 1  HOUR,  1.5000, 230.0, 6.52),
(1, 1, NOW() - INTERVAL 2  HOUR,  1.4800, 229.5, 6.44),
(1, 1, NOW() - INTERVAL 3  HOUR,  1.5100, 230.2, 6.57),
(1, 1, NOW() - INTERVAL 4  HOUR,  1.4600, 229.0, 6.35),
(2, 2, NOW() - INTERVAL 1  HOUR,  0.0600, 230.0, 0.26),
(2, 2, NOW() - INTERVAL 2  HOUR,  0.0610, 230.0, 0.27),
(3, NULL, NOW() - INTERVAL 30 MINUTE, 0.1000, 230.0, 0.43);

INSERT INTO Alert (device_id, alert_type, alert_message, threshold_value, status) VALUES
(1, 'High Usage',         'AC unit exceeding 1.4 kWh threshold',         1.40, 'active'),
(3, 'Device Malfunction', 'Projector reporting irregular current draw',   0.50, 'resolved');

INSERT INTO Energy_Report (building_id, report_date, total_energy_kwh, peak_usage_time, carbon_emission_estimate) VALUES
(1, CURDATE() - INTERVAL 1 DAY, 48.2500, (NOW() - INTERVAL 1 DAY) + INTERVAL 14 HOUR, 22.1950),
(1, CURDATE(),                  12.4000,  NOW() - INTERVAL 2 HOUR,                      5.7040)
ON DUPLICATE KEY UPDATE
    total_energy_kwh         = VALUES(total_energy_kwh),
    peak_usage_time          = VALUES(peak_usage_time),
    carbon_emission_estimate = VALUES(carbon_emission_estimate);
