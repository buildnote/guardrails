defmodule Company.Core.MixProject do
  use Mix.Project

  def project do
    [app: :core, version: "2.0.0"]
  end

  defp deps do
    [{:telemetry, "1.2.1"}]
  end
end
