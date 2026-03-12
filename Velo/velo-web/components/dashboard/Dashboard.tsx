"use client";

import { useState } from "react";
import {
    Bluetooth,
    Zap,
    BatteryCharging,
    MapPin,
    Settings as SettingsIcon,
    Signal,
    Play,
    Square,
} from "lucide-react";
import clsx from "clsx";
import { useBluetooth } from "../BluetoothContext";
import { useRide } from "../RideContext";
import { SettingsModal } from "../SettingsModal";
import { StatCard } from "./StatCard";
import { HeroCard } from "./HeroCard";
import { ControlCenter } from "./ControlCenter";
import { InsightsPanel } from "./InsightsPanel";

function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
}

export const Dashboard = () => {
    const { isConnected, connect, speed, battery, tripDistance } = useBluetooth();
    const { isRiding, startRide, stopRide, elapsedTime } = useRide();
    const [showSettings, setShowSettings] = useState(false);

    const tripKm = (tripDistance / 1000).toFixed(1);

    return (
        <div className="flex flex-col font-sans selection:bg-[#ccff00] selection:text-black">
            <main className="flex-1 bento-grid pb-28">
                {/* Header */}
                <header className="flex justify-between items-center py-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full border-2 border-[#ccff00] flex items-center justify-center">
                            <span className="text-[#ccff00] font-bold text-xs">O</span>
                        </div>
                        <h1 className="text-lg font-bold tracking-tight">Opensens Velo</h1>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Settings */}
                        <button
                            onClick={() => setShowSettings(true)}
                            className="p-2 bg-[#161616] border border-[#333] rounded-full text-gray-400 hover:text-white hover:border-white transition-all"
                        >
                            <SettingsIcon size={18} />
                        </button>

                        {/* Connect */}
                        <button
                            onClick={connect}
                            className={clsx(
                                "flex items-center gap-2 px-3 py-1.5 rounded-full transition-all border",
                                isConnected
                                    ? "bg-[#ccff00]/10 border-[#ccff00] text-[#ccff00]"
                                    : "bg-[#222] border-[#333] text-gray-400 animate-pulse hover:bg-[#333]"
                            )}
                        >
                            {isConnected && <Signal size={14} />}
                            <Bluetooth size={18} />
                            <span className="text-xs font-bold">{isConnected ? "Connected" : "Connect"}</span>
                        </button>
                    </div>
                </header>

                <HeroCard />

                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-3">
                    <StatCard label="Speed" value={speed.toFixed(1)} unit="km/h" icon={Zap} type="speed" />
                    <StatCard label="Battery" value={battery} unit="%" icon={BatteryCharging} type="battery" />
                    <StatCard
                        label="Trip"
                        value={tripKm}
                        unit="km"
                        icon={MapPin}
                        sub={isRiding ? formatTime(elapsedTime) : undefined}
                    />
                </div>

                {/* Ride Start/Stop */}
                <button
                    onClick={isRiding ? stopRide : startRide}
                    className={clsx(
                        "w-full py-3.5 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
                        isRiding
                            ? "bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30"
                            : "bg-[#ccff00]/10 border border-[#ccff00]/50 text-[#ccff00] hover:bg-[#ccff00]/20"
                    )}
                >
                    {isRiding ? <Square size={16} /> : <Play size={16} />}
                    {isRiding ? `Stop Ride (${formatTime(elapsedTime)})` : "Start Ride"}
                </button>

                <InsightsPanel />

                <ControlCenter />
            </main>

            <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
        </div>
    );
};
