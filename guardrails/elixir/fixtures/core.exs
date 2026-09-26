defmodule Company.Core.MixProject do
  use Mix.Project

  def project do
    [app: :core, version: "2.0.0", deps: deps()]
  end

  defp deps do
    [
      {:telemetry, "~> 1.2"},
      {:widget_ui, github: "company/widget_ui", branch: "main"}
    ]
  end
end
