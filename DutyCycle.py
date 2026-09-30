class DutyCycle:
    """
    Gestionnaire du Duty Cycle de la cuve de chauffe pour PastoWeb.
    - get() : renvoie la valeur brute du DERNIER cycle individuel complété.
    - average() : renvoie la MOYENNE LISSÉE (Sample & Hold) pondérée sur la fenêtre.
    """
    def __init__(self, period_sec: float, smoothing_duration_sec: float):
        self.period = float(period_sec)
        self.smoothing_duration = float(smoothing_duration_sec)

        self.current_state = None  # 1 (ON), 0 (OFF), None (Inactif/Panne)
        self.last_timestamp = None
        self.state_start_ts = None

        # Historique des cycles complétés : [(dc_val, duration, timestamp)]
        self.completed_cycles = []

        # Suivi du dernier cycle individuel complété (pour get())
        self.last_completed_cycle = (None, None)

        # Suivi de la tranche d'état courante et du cycle
        self.cycle_start_state = None
        self.cycle_has_switched = False
        self.time_on = 0.0
        self.time_off = 0.0

        # Valeur moyenne lissée maintenue (pour average())
        self.stable_duty = None
        self.stable_timestamp = None

        self.cleaning_required = False

    def record(self, state, timestamp: float):
        timestamp = float(timestamp)

        # CAS 1 : Inactif ou Panne
        if state is None:
            self.current_state = None
            self.last_timestamp = timestamp
            self._reset()
            return

        # CAS 2 : Initialisation
        if self.current_state is None:
            self.current_state = state
            self.last_timestamp = timestamp
            self.state_start_ts = timestamp
            self.cycle_start_state = state
            self.cycle_has_switched = False
            self.time_on = 0.0
            self.time_off = 0.0
            return

        dt = timestamp - self.last_timestamp
        if dt < 0:
            dt = 0.0

        prev_state = self.current_state
        self.current_state = state
        self.last_timestamp = timestamp

        if state != prev_state:
            self.state_start_ts = timestamp

        # Accumulation du temps dans le cycle d'hystérésis en cours
        if prev_state == 1:
            self.time_on += dt
        elif prev_state == 0:
            self.time_off += dt

        # Détection de bascule d'état (0->1 ou 1->0)
        if prev_state != state:
            # Si on boucle un cycle d'hystérésis complet (ex: ON -> OFF -> ON)
            if state == self.cycle_start_state and self.cycle_has_switched:
                tot = self.time_on + self.time_off
                if tot > 0:
                    dc_val = self.time_on / tot
                    # Stockage du DERNIER cycle individuel pour get()
                    self.last_completed_cycle = (dc_val, timestamp)
                    self.completed_cycles.append((dc_val, tot, timestamp))
                    self._cleanup(timestamp)

                # Démarrage d'un nouveau cycle
                self.cycle_start_state = state
                self.cycle_has_switched = False
                self.time_on = 0.0
                self.time_off = 0.0
            else:
                self.cycle_has_switched = True

            # Mise à jour de la MOYENNE LISSÉE (pour average()) à chaque bascule
            self._update_stable_duty(timestamp)

        # Gestion des arrêts/chauffe continus (> smoothing_duration)
        if self.state_start_ts is not None:
            dur = timestamp - self.state_start_ts
            if dur >= self.smoothing_duration:
                forced = 1.0 if self.current_state == 1 else 0.0
                self.stable_duty = forced
                self.stable_timestamp = timestamp
                # En cas de blocage continu 0% ou 100%, get() s'aligne aussi
                self.last_completed_cycle = (forced, timestamp)

    def _reset(self):
        self.state_start_ts = None
        self.completed_cycles.clear()
        self.last_completed_cycle = (None, None)
        self.cycle_start_state = None
        self.cycle_has_switched = False
        self.time_on = 0.0
        self.time_off = 0.0
        self.stable_duty = None
        self.stable_timestamp = None

    def _cleanup(self, ts: float):
        cutoff = ts - self.smoothing_duration
        self.completed_cycles = [c for c in self.completed_cycles if c[2] >= cutoff]

    def _update_stable_duty(self, ts: float):
        self._cleanup(ts)
        if self.completed_cycles:
            tot_w_dc = sum(dc * dur for dc, dur, t in self.completed_cycles)
            tot_w = sum(dur for dc, dur, t in self.completed_cycles)
            if tot_w > 0:
                self.stable_duty = tot_w_dc / tot_w
                self.stable_timestamp = ts
        else:
            tot = self.time_on + self.time_off
            if tot > 0:
                self.stable_duty = self.time_on / tot
                self.stable_timestamp = ts

    def get(self) -> tuple:
        """
        Retourne (valeur, timestamp) du DERNIER cycle individuel complété.
        """
        if self.current_state is None:
            return (None, None)
        return self.last_completed_cycle

    def average(self) -> tuple:
        """
        Retourne (valeur, timestamp) de la MOYENNE LISSÉE pondérée sur la fenêtre.
        """
        if self.current_state is None:
            return (None, None)
        return (self.stable_duty, self.stable_timestamp)

def main():
    # Instanciation : vérification toutes les 3s, lissage sur 120s
    dc = DutyCycle(period_sec=3.0, smoothing_duration_sec=120.0)

    print("=" * 80)
    print("TEST VISUEL DU DUTY CYCLE (PastoWeb)")
    print("=" * 80)

    current_time = 0.0

    def simulate(state, duration_sec, label):
        nonlocal current_time
        print(f"\n>>> SCÉNARIO : {label} ({duration_sec}s avec state={state})")
        steps = int(duration_sec / 3.0)
        for i in range(steps):
            current_time += 3.0
            dc.record(state, current_time)
            get_val, _ = dc.get()
            avg_val, _ = dc.average()

            get_str = f"{get_val*100:5.1f}%" if get_val is not None else "  None"
            avg_str = f"{avg_val*100:5.1f}%" if avg_val is not None else "  None"

            # Affichage synthétique toutes les 15s ou lors des transitions
            if i == 0 or i == steps - 1 or (i + 1) % 5 == 0:
                print(f"  [t={current_time:5.1f}s] State={str(state):4s} | get() [Dernier complet]: {get_str} | average() [Lissé]: {avg_str}")

    # SÉQUENCE DE TEST :
    # 1. Première chauffe (30s)
    simulate(state=1, duration_sec=30, label="1. Chauffe initiale ON (30s)")

    # 2. Refroidissement (60s)
    simulate(state=0, duration_sec=60, label="2. Refroidissement OFF (60s)")

    # 3. Réallumage (30s) -> Ferme le 1er cycle complet (30s ON + 60s OFF = 90s total, duty = 33.3%)
    simulate(state=1, duration_sec=30, label="3. Re-chauffe ON (30s) -> Doit clore le 1er cycle à 33.3%")

    # 4. Refroidissement plus long (90s)
    simulate(state=0, duration_sec=90, label="4. Refroidissement OFF (90s)")

    # 5. Réallumage (15s) -> Ferme le 2e cycle complet (30s ON + 90s OFF = 120s total, duty = 25.0%)
    simulate(state=1, duration_sec=15, label="5. Re-chauffe ON (15s) -> Doit clore le 2e cycle à 25.0%")

    # 6. Cuve bloquée à 100% ON pendant 120s (> durée de lissage -> monte à 100%)
    simulate(state=1, duration_sec=120, label="6. Chauffe continue 100% ON (> 120s lissage)")
    # Une deuxième fois pour voir !
    simulate(state=1, duration_sec=120, label="6.b Chauffe continue 100% ON encore un peu!")

    # 7. Passage du contrôle à None (Panne / Inactif)
    simulate(state=None, duration_sec=15, label="7. Contrôle inactif (state=None)")

if __name__ == "__main__":
    main()
